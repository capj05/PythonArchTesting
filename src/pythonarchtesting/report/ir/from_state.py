"""Build typed report IR directly from execution state objects."""

import importlib.metadata
import json
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from pythonarchtesting.config import load_config
from pythonarchtesting.config.accessors import (
    get_bool,
    get_float,
    get_int,
    get_list,
    get_section,
    get_str,
)
from pythonarchtesting.exceptions import ReportGenerationError
from pythonarchtesting.matching import MatchingConfig
from pythonarchtesting.run_state import RunState, TargetRunState

from ..policy import (
    compute_aggregate_exit_code,
    compute_target_exit_code,
)
from ..schema_v2 import validate_report_schema_v2
from .models import (
    AggregateSummary,
    MatchingSection,
    ReportDocument,
    RunMeta,
    TargetReport,
)
from .normalize import (
    matching_summary,
    result_item,
    results_summary,
    split_qualname,
)
from .order import SEV_RANK, STAT_RANK, sort_matches, sort_results, sort_targets
from .serialize import to_legacy_schema_v2
from .summary import build_results_summary
from .target_ids import normalize_target_ids

_VALIDATIONRESULT_FIELD_MAP = {
    "src_module": "src_package",
    "src_qualname": "src_function_name",
    "src_filepath": "src_file",
    "src_lineno": "src_line_num",
}

_RESULT_TIMING_KEYS = (
    "duration",
    "elapsed",
    "execution_time",
    "time_ms",
    "phase_duration",
)
STATIC_ANALYSIS_MODE = "static-only"
# Statuses that count towards "Top Rules by Violation Count".


def _analysis_mode(run_state: RunState) -> str:
    """``static-only``, or ``dynamic (sandbox: limits)`` when target code ran."""
    if not getattr(run_state, "dynamic_enabled", False):
        return STATIC_ANALYSIS_MODE
    sandbox = getattr(getattr(run_state, "sandbox", None), "mode", None)
    return f"dynamic (sandbox: {sandbox})" if sandbox else "dynamic"


def _getattr_required(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name)
    except AttributeError as exc:
        raise ReportGenerationError(
            f"Missing field on {type(obj).__name__}: {name}"
        ) from exc


def _normalize_status(value: Any) -> str:
    if hasattr(value, "value"):
        value = value.value
    if value is None:
        return ""
    text = str(value)
    lower = text.lower()
    mapping = {
        "ok": "OK",
        "failed": "FAILED",
        "error": "ERROR",
        "warning": "WARNING",
        "skipped": "SKIPPED",
    }
    return mapping.get(lower, text.upper())


def _serialize_validation_result(vr: Any) -> Dict[str, Any]:
    src = {
        out: _getattr_required(vr, attr)
        for out, attr in _VALIDATIONRESULT_FIELD_MAP.items()
    }
    return {
        "status": _normalize_status(_getattr_required(vr, "status")),
        "check_type": _getattr_required(vr, "check_type"),
        "description": _getattr_required(vr, "description"),
        "source": {
            "module": src["src_module"],
            "qualname": src["src_qualname"],
            "file": src["src_filepath"],
            "line": src["src_lineno"],
        },
        "target": {
            "module": _getattr_required(vr, "target_package"),
            "qualname": _getattr_required(vr, "target_function_name"),
        },
        "details": _getattr_required(vr, "details"),
        "timestamp": _getattr_required(vr, "timestamp"),
    }


def now_utc_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _framework_version() -> str:
    try:
        return importlib.metadata.version("pythonarchtesting")
    except Exception:
        return "unknown"


def _get_config_bool(config: Any, section: str, key: str, default: bool) -> bool:
    return get_bool(config, section, key, default)


def _get_config_int(config: Any, section: str, key: str, default: int) -> int:
    return get_int(config, section, key, default)


def _get_config_float(config: Any, section: str, key: str, default: float) -> float:
    return get_float(config, section, key, default)


def _get_config_list(config: Any, section: str, key: str, default: list) -> list:
    return get_list(config, section, key, default)


def _get_config_str(config: Any, section: str, key: str, default: str) -> str:
    return get_str(config, section, key, default)


def _maybe_config_snapshot(
    config: Any,
) -> Optional[Dict[str, Dict[str, str]]]:
    include = _get_config_bool(config, "report", "include_config_snapshot", False)
    if not include:
        return None
    raw = getattr(config, "raw", None)
    if isinstance(raw, dict) and raw:
        raw_snapshot: Dict[str, Dict[str, str]] = {}
        for section_name, section_values in raw.items():
            if not isinstance(section_values, dict):
                continue
            raw_snapshot[str(section_name)] = {
                str(key): str(value) for key, value in section_values.items()
            }
        if raw_snapshot:
            return raw_snapshot
    get_all_fn = getattr(config, "get_all", None)
    if callable(get_all_fn):
        snapshot_data = get_all_fn()
        if isinstance(snapshot_data, dict):
            normalized_snapshot: Dict[str, Dict[str, str]] = {}
            for section_name, section_values in snapshot_data.items():
                if not isinstance(section_values, dict):
                    continue
                normalized_snapshot[str(section_name)] = {
                    str(key): str(value) for key, value in section_values.items()
                }
            if normalized_snapshot:
                return normalized_snapshot
    sections = (
        "discovery",
        "logging",
        "report",
        "projects",
        "matching",
    )
    snapshot_by_section: Dict[str, Dict[str, str]] = {}
    for section in sections:
        section_data = get_section(config, section)
        if section_data:
            snapshot_by_section[section] = {
                str(key): str(value) for key, value in section_data.items()
            }
    return snapshot_by_section or None


def _severity_from_status(status: str) -> str:
    if status in {"FAILED", "ERROR"}:
        return "error"
    if status in {"WARNING", "SKIPPED"}:
        return "warning"
    return "info"


def _display_path(value: Any) -> str:
    """Render a path relative to the working directory when it lives inside it.

    Keeps reports reproducible across machines: a run made from the project root
    reports ``example/reference`` rather than a checkout-specific absolute path.
    Paths outside the working directory stay absolute, because shortening them
    would be misleading.
    """
    path = Path(value)
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return str(path)


def _derive_project_id(project_id: Optional[str], target_path: Optional[str]) -> str:
    if project_id:
        return str(project_id)
    if target_path:
        return str(target_path).rstrip("/\\").split("/")[-1].split("\\")[-1] or "single"
    return "single"


def _derive_category(rule_type: Optional[str], rule_id: Optional[str]) -> str:
    value = (rule_type or rule_id or "unknown").strip()
    if not value:
        return "unknown"
    return value.split("/", 1)[0]


def _derive_tags(details: Dict[str, Any]) -> List[str]:
    tags = details.get("tags")
    if isinstance(tags, list):
        return sorted({str(tag) for tag in tags if str(tag).strip()})
    return []


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _timing_seconds_from_details(details: Dict[str, Any]) -> Optional[float]:
    for key in _RESULT_TIMING_KEYS:
        if key not in details:
            continue
        val = _as_float(details.get(key))
        if val is None:
            continue
        if key.endswith("_ms"):
            return val / 1000.0
        return val
    return None


def _entity_location(entity: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    src = entity or {}
    class_name, function_name = split_qualname(src.get("qualname"))
    return {
        "module": src.get("module"),
        "qualname": src.get("qualname"),
        "file": src.get("file"),
        "line": src.get("line"),
        "class": class_name,
        "function": function_name,
    }


def _matching_section(
    matches: Iterable[Dict[str, Any]], config: Dict[str, Any]
) -> MatchingSection:
    ordered_matches = tuple(sort_matches(matches))
    return MatchingSection(
        matches=ordered_matches,
        matching_config=dict(config),
        summary=matching_summary(ordered_matches),
    )


def _config_fingerprint(config_snapshot: Optional[Dict[str, Any]]) -> Optional[str]:
    if not config_snapshot:
        return None
    payload = json.dumps(
        config_snapshot, sort_keys=True, default=str, separators=(",", ":")
    )
    return sha1(payload.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _validate_report_document(
    document: ReportDocument,
    config: Any,
    validate_report_schema_v2_fn: Callable[[Any], List[str]],
) -> None:
    if not _get_config_bool(config, "report", "validate_schema_v2", False):
        return
    errors = validate_report_schema_v2_fn(to_legacy_schema_v2(document))
    if errors:
        raise ReportGenerationError(
            "Report schema v2 validation failed: " + "; ".join(errors)
        )


def _result_id(project_id: str, item: Dict[str, Any]) -> str:
    key = "|".join(
        [
            project_id,
            str(item.get("rule_id") or ""),
            str(item.get("source_entity_id") or ""),
            str(item.get("target_entity_id") or ""),
            str(item.get("status") or ""),
        ]
    )
    return sha1(key.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _stable_payload_key(payload: Any) -> str:
    try:
        return json.dumps(payload, sort_keys=True, default=str)
    except TypeError:
        return repr(payload)


def _evidence_sort_key(ev: Dict[str, Any]) -> Tuple[Any, ...]:
    loc = ev.get("location") or {}
    file_value = loc.get("file")
    line_value = loc.get("line")
    return (
        ev.get("type", ""),
        file_value is None,
        file_value or "",
        line_value is None,
        line_value if line_value is not None else 0,
        _stable_payload_key(ev.get("payload", {})),
    )


def _sort_evidence(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=_evidence_sort_key)


def _sort_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def candidate_key(candidate: Dict[str, Any]) -> Tuple[Any, ...]:
        breakdown = candidate.get("breakdown") or {}
        module_distance = breakdown.get("module_distance", 10**9)
        confidence_raw = candidate.get("confidence")
        try:
            confidence_val = (
                float(confidence_raw) if confidence_raw is not None else 0.0
            )
        except (TypeError, ValueError):
            confidence_val = 0.0
        return (
            -confidence_val,
            module_distance,
            candidate.get("target_entity_id") or "",
        )

    return sorted(candidates, key=candidate_key)


def _sort_matches(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(matches, key=lambda m: m.get("source_entity_id") or "")


def _sort_results(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        items,
        key=lambda r: (
            SEV_RANK.get(str(r.get("severity") or ""), 9),
            STAT_RANK.get(str(r.get("status") or ""), 9),
            r.get("rule_id") or "",
            r.get("source_entity_id") or "",
            r.get("target_entity_id") or "",
        ),
    )


def _normalize_evidence(raw: Any) -> List[Dict[str, Any]]:
    if not raw:
        return []
    normalized: List[Dict[str, Any]] = []

    for item in raw:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload", {})
        if not isinstance(payload, dict):
            payload = {"value": payload}

        for key in ("evidence_id", "source", "role", "entity_id"):
            if key in item and key not in payload:
                payload[key] = item[key]

        location_raw = item.get("location")
        location: Optional[Dict[str, Any]] = None
        if isinstance(location_raw, dict):
            file_value = location_raw.get("file") or location_raw.get("filepath")
            line_value = location_raw.get("line")
            if line_value is None:
                line_value = location_raw.get("lineno")
            if file_value is not None or line_value is not None:
                location = {"file": file_value, "line": line_value}

        if location is None and isinstance(payload, dict):
            file_value = payload.get("filepath")
            line_value = payload.get("lineno")
            if file_value is not None or line_value is not None:
                location = {"file": file_value, "line": line_value}

        normalized.append(
            {
                "type": item.get("type", ""),
                "payload": payload,
                "location": location,
            }
        )

    return _sort_evidence(normalized)


def _candidate_to_report(candidate: Any) -> Dict[str, Any]:
    if isinstance(candidate, dict):
        data = dict(candidate)
        if "target_entity_id" not in data and "target_id" in data:
            data["target_entity_id"] = data.get("target_id")
        if data.get("confidence") is not None:
            data["confidence"] = round(float(data["confidence"]), 6)
        return data
    data = {
        "target_entity_id": getattr(candidate, "target_id", None),
        "confidence": round(float(getattr(candidate, "confidence", 0.0)), 6),
        "breakdown": getattr(candidate, "breakdown", {}) or {},
        "tie_break": list(getattr(candidate, "tie_break", ())),
    }
    return data


def _entity_report(entity: Any) -> Dict[str, Any]:
    if entity is None:
        return {
            "module": None,
            "qualname": None,
            "file": None,
            "line": None,
        }
    return {
        "module": getattr(entity, "module_path", None),
        "qualname": getattr(entity, "qualname", None),
        "file": getattr(entity, "filepath_rel", None),
        "line": getattr(entity, "lineno", None),
    }


def _should_suppress_target_display(match_status: Any) -> bool:
    status = str(match_status or "").strip().lower()
    return status in {"low_confidence", "unmatched"}


def _rule_meta_lookup_from_lists(rules: List[Any]) -> Dict[str, Dict[str, Any]]:
    meta: Dict[str, Dict[str, Any]] = {}
    for rule in rules or []:
        meta[rule.rule_id] = {
            "severity": getattr(rule, "severity", None),
            "fix_hints": list(getattr(rule, "fix_hints", ()) or ()),
            "rule_type": getattr(rule, "rule_type", None),
            "activation_source": getattr(rule, "activation_source", None),
        }
    return meta


def _rule_activation_source(
    meta: Dict[str, Any], details: Dict[str, Any]
) -> Optional[str]:
    """The activation source of a rule result.

    The rule's metadata decides; a string the result carries in its details
    stands in when the metadata has none.
    """
    activation_source = meta.get("activation_source")
    if not activation_source:
        details_activation = details.get("activation_source")
        if isinstance(details_activation, str):
            activation_source = details_activation
    return activation_source


def _rule_evidence(result: Any) -> List[Dict[str, Any]]:
    """The evidence of a rule result as plain dicts, normalised and sorted.

    The dicts share each evidence's ``payload`` object, so normalising adds
    the evidence's identity keys to that payload in place.
    """
    evidence_raw = [
        {
            "evidence_id": ev.evidence_id,
            "type": ev.type,
            "source": ev.source,
            "role": ev.role,
            "entity_id": ev.entity_id,
            "payload": ev.payload,
            "location": ev.location,
        }
        for ev in result.evidence
    ]
    return _normalize_evidence(evidence_raw)


def _rule_result_item(
    result: Any,
    meta: Dict[str, Any],
    source_by_id: Dict[str, Any],
    target_by_id: Dict[str, Any],
) -> Dict[str, Any]:
    """The report item of one rule result, before ``_enrich``.

    A skipped result is a warning whatever the rule's severity, and the target
    is not shown when the match was too weak to name one.
    """
    status = _normalize_status(result.status)
    severity = meta.get("severity") or _severity_from_status(status)
    if status == "SKIPPED":
        severity = "warning"
    details_payload = dict(result.details)
    source_entity = source_by_id.get(result.source_entity_id)
    target_entity = (
        target_by_id.get(result.target_entity_id) if result.target_entity_id else None
    )
    if _should_suppress_target_display(result.match_status):
        target_entity = None
    return {
        "rule_id": result.rule_id,
        "rule_type": meta.get("rule_type"),
        "status": status,
        "severity": severity,
        "message": result.message,
        "source_entity_id": result.source_entity_id,
        "target_entity_id": result.target_entity_id,
        "match_status": result.match_status,
        "confidence": round(float(result.confidence), 6),
        "source": _entity_report(source_entity),
        "target": _entity_report(target_entity),
        "evidence": _rule_evidence(result),
        "details": details_payload,
        "fix_hints": meta.get("fix_hints", []),
        "activation_source": _rule_activation_source(meta, details_payload),
    }


def _validation_parts(vr: Any) -> Tuple[Dict[str, Any], Dict[str, Any], Any]:
    """The serialized validation result, a copy of its details, its evidence.

    The evidence is popped from the copy, never from the result's own details,
    so the report's details leave it out without changing the input.
    """
    serialized = _serialize_validation_result(vr)
    details = serialized.get("details")
    if not isinstance(details, dict):
        details = {}
    else:
        details = dict(details)
    evidence_raw = details.pop("evidence", None)
    return serialized, details, evidence_raw


def _validation_rule_id(serialized: Dict[str, Any], details: Dict[str, Any]) -> Any:
    """The rule id a validation result reports: its own, else its check type."""
    return details.get("rule_id") or serialized.get("check_type")


def _validation_key(
    serialized: Dict[str, Any], details: Dict[str, Any]
) -> Tuple[Any, Any, Any]:
    """The key that tells a validation result already reported by a rule.

    An entity id in the details is used as is (even ``None``); without one the
    entity is identified by its location.
    """
    if "source_entity_id" in details:
        source_identity = details.get("source_entity_id")
    else:
        src = serialized.get("source") or {}
        source_identity = (
            f"{src.get('module')}:{src.get('qualname')}:"
            f"{src.get('file')}:{src.get('line')}"
        )
    if "target_entity_id" in details:
        target_identity = details.get("target_entity_id")
    else:
        tgt = serialized.get("target") or {}
        target_identity = f"{tgt.get('module')}:{tgt.get('qualname')}"
    return (_validation_rule_id(serialized, details), source_identity, target_identity)


def _location(entity: Any) -> Dict[str, Any]:
    """The module, qualname, file and line of a serialized entity location."""
    src = entity or {}
    return {
        "module": src.get("module"),
        "qualname": src.get("qualname"),
        "file": src.get("file"),
        "line": src.get("line"),
    }


def _validation_confidence(details: Dict[str, Any]) -> Optional[float]:
    """The confidence in the details, rounded, or ``None`` when not a number."""
    parsed_confidence = _as_float(details.get("confidence"))
    if parsed_confidence is None:
        return None
    return round(parsed_confidence, 6)


def _validation_result_item(
    vr: Any,
    serialized: Dict[str, Any],
    details: Dict[str, Any],
    evidence_raw: Any,
) -> Dict[str, Any]:
    """The report item of one legacy validation result, before ``_enrich``.

    Built only for a result no rule result already reported, so its evidence
    is normalised only then.
    """
    status = _normalize_status(serialized.get("status"))
    match_status = details.get("match_status")
    return {
        "rule_id": _validation_rule_id(serialized, details),
        "rule_type": serialized.get("check_type"),
        "status": status,
        "severity": _severity_from_status(status),
        "message": serialized.get("description"),
        "source_entity_id": details.get("source_entity_id"),
        "target_entity_id": details.get("target_entity_id"),
        "match_status": match_status,
        "confidence": _validation_confidence(details),
        "source": _location(serialized.get("source")),
        "target": (
            _entity_report(None)
            if _should_suppress_target_display(match_status)
            else _location(serialized.get("target"))
        ),
        "evidence": _normalize_evidence(evidence_raw),
        "details": details,
        "fix_hints": ([vr.suggestion] if getattr(vr, "suggestion", None) else []),
        "timestamp": serialized.get("timestamp"),
        "check_type": serialized.get("check_type"),
        "activation_source": details.get("activation_source"),
    }


def _enrich(item: Dict[str, Any], project_id: str) -> None:
    """Add the fields every report item derives from the others, in place.

    ``result_id`` comes last because it hashes the fields set before it.
    """
    details = item.get("details")
    if not isinstance(details, dict):
        details = {}
        item["details"] = details
    item["project_id"] = project_id
    item["category"] = _derive_category(
        str(item.get("rule_type") or ""), str(item.get("rule_id") or "")
    )
    item["tags"] = _derive_tags(details)
    item["timing_seconds"] = _timing_seconds_from_details(details)
    item["locations"] = {
        "source": _entity_location(item.get("source")),
        "target": _entity_location(item.get("target")),
    }
    item["result_id"] = _result_id(project_id, item)


def _build_results(
    *,
    rule_results: List[Any],
    validation_results: List[Any],
    rule_meta: Dict[str, Dict[str, Any]],
    source_by_id: Dict[str, Any],
    target_by_id: Dict[str, Any],
    project_id: str,
) -> List[Dict[str, Any]]:
    """The report items of the rule results and legacy validation results.

    A validation result that a rule result already reports (same rule, source
    and target) is left out; validation results are not deduplicated among
    themselves.
    """
    results: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[Any, Any, Any]] = set()
    for result in rule_results or []:
        meta = rule_meta.get(result.rule_id, {})
        item = _rule_result_item(result, meta, source_by_id, target_by_id)
        seen_keys.add(
            (result.rule_id, result.source_entity_id, result.target_entity_id)
        )
        results.append(item)

    for vr in validation_results:
        serialized, details, evidence_raw = _validation_parts(vr)
        if _validation_key(serialized, details) in seen_keys:
            continue
        results.append(_validation_result_item(vr, serialized, details, evidence_raw))

    for item in results:
        _enrich(item, project_id)
    return _sort_results(results)


def _build_matching_section_for_target(
    target_state: TargetRunState,
    config: Any,
) -> Dict[str, Any]:
    matches: List[Dict[str, Any]] = []
    for match in target_state.match_results:
        status = (
            match.status.value if hasattr(match.status, "value") else str(match.status)
        )
        candidates = [_candidate_to_report(c) for c in match.candidates]
        candidates = _sort_candidates(candidates)
        matches.append(
            {
                "source_entity_id": match.source_id,
                "target_entity_id": match.target_id,
                "status": status,
                "confidence": round(float(match.confidence), 6),
                "candidates": candidates,
                "reasons": list(match.reasons),
            }
        )

    matching_cfg = MatchingConfig.from_config(config)
    return {
        "matches": _sort_matches(matches),
        "matching_config": {
            "threshold": matching_cfg.threshold,
            "delta": matching_cfg.delta,
            "min_candidate": matching_cfg.min_candidate,
            "top_n": matching_cfg.top_n,
            "max_fuzzy_candidates": matching_cfg.max_fuzzy_candidates,
            "max_stage2_candidates": matching_cfg.max_stage2_candidates,
            "max_stage3_candidates": matching_cfg.max_stage3_candidates,
        },
    }


def _build_results_section_for_target(
    run_state: RunState,
    target_state: TargetRunState,
    config: Any,
) -> List[Dict[str, Any]]:
    rule_meta = _rule_meta_lookup_from_lists(run_state.rules)
    return _build_results(
        rule_results=target_state.rule_results,
        validation_results=target_state.validation_results,
        rule_meta=rule_meta,
        source_by_id=run_state.source_by_id,
        target_by_id=target_state.target_by_id,
        project_id=target_state.target_id,
    )


def _format_datetime_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_run_report_document(
    run_state: RunState,
    target_states: List[TargetRunState],
    config: Optional[Any],
    *,
    validate_report_schema_v2_fn: Callable[[Any], List[str]],
) -> ReportDocument:
    cfg = config or run_state.config or load_config()
    generated_at = _format_datetime_z(run_state.run_generated_at)
    config_snapshot = _maybe_config_snapshot(cfg)
    run = RunMeta(
        generated_at=generated_at,
        target_path=None,
        source_path=_display_path(run_state.source_path),
        reference_modules=tuple(sorted(str(v) for v in run_state.reference_modules)),
        config_snapshot=config_snapshot,
        config_fingerprint=_config_fingerprint(config_snapshot),
        tool_version=run_state.framework_version,
        mode=_analysis_mode(run_state),
        principle=run_state.principle,
    )

    target_id_map = normalize_target_ids(
        [
            {"target_id": target.target_id, "target_path": str(target.target_path)}
            for target in target_states
        ]
    )
    targets: List[TargetReport] = []
    combined_results_payload: List[Dict[str, Any]] = []

    for target_state in target_states:
        matching_payload = _build_matching_section_for_target(target_state, cfg)
        results_payload = _build_results_section_for_target(
            run_state, target_state, cfg
        )
        target_summary_payload = build_results_summary(results_payload)
        exit_code = compute_target_exit_code(results_payload, cfg)
        target_state.exit_code = exit_code
        combined_results_payload.extend(results_payload)
        original_target_id = str(target_state.target_id)
        target_path = str(target_state.target_path)
        canonical_target_id, display_name = target_id_map.get(
            (original_target_id, target_path),
            (original_target_id, original_target_id),
        )
        targets.append(
            TargetReport(
                target_id=canonical_target_id,
                display_name=display_name,
                source_root=run.source_path,
                target_path=_display_path(target_path),
                tags=tuple(),
                mode=run.mode,
                matching=_matching_section(
                    matching_payload.get("matches") or [],
                    matching_payload.get("matching_config") or {},
                ),
                results=tuple(
                    sort_results([result_item(item) for item in results_payload])
                ),
                summary=results_summary(target_summary_payload),
                artifacts=tuple(),
                exit_code=exit_code,
            )
        )

    targets = sort_targets(targets)
    failed = sum(1 for target in target_states if target.exit_code == 1)
    aggregate_exit_code = compute_aggregate_exit_code(target_states, cfg)
    document = ReportDocument(
        schema_version="2",
        framework_version=run_state.framework_version,
        generated_at=generated_at,
        run=run,
        targets=tuple(targets),
        summary=AggregateSummary(
            targets_total=len(target_states),
            targets_failed=failed,
            targets_passed=len(target_states) - failed,
            results=results_summary(build_results_summary(combined_results_payload)),
        ),
        exit_code=aggregate_exit_code,
        kind="run",
    )
    _validate_report_document(document, cfg, validate_report_schema_v2_fn)
    return document


def build_run_report_document(
    run_state: RunState,
    target_states: List[TargetRunState],
    config: Optional[Any] = None,
    *,
    validate_report_schema_v2_fn: Callable[[Any], List[str]] = (
        validate_report_schema_v2
    ),
) -> ReportDocument:
    """Build the typed IR document for a run report."""
    return _build_run_report_document(
        run_state,
        target_states,
        config,
        validate_report_schema_v2_fn=validate_report_schema_v2_fn,
    )
