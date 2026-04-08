"""Normalize legacy schema-v2 report dictionaries into typed IR."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import (
    AggregateSummary,
    EntityRef,
    EvidenceItem,
    MatchingSection,
    MatchingSummary,
    ReportDocument,
    ResultItem,
    ResultsSummary,
    RunMeta,
    TargetReport,
)
from .order import sort_matches, sort_results, sort_targets
from .summary import build_results_summary
from .target_ids import normalize_target_ids, slugify_target_id


def _split_qualname(qualname: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not qualname:
        return None, None
    parts = [p for p in str(qualname).split(".") if p and p != "<locals>"]
    if not parts:
        return None, None
    if len(parts) == 1:
        return None, parts[0]
    return parts[-2], parts[-1]


def _entity_ref(value: Optional[Dict[str, Any]]) -> EntityRef:
    src = value or {}
    cls, function = _split_qualname(src.get("qualname"))
    return EntityRef(
        module=src.get("module"),
        qualname=src.get("qualname"),
        file=src.get("file"),
        line=src.get("line"),
        cls=cls,
        function=function,
    )


def _evidence_item(value: Dict[str, Any]) -> EvidenceItem:
    location = value.get("location") or {}
    payload = value.get("payload")
    if not isinstance(payload, dict):
        payload = {"value": payload}
    evidence_id = payload.get("evidence_id")
    return EvidenceItem(
        type=str(value.get("type") or ""),
        payload=dict(payload),
        location_file=location.get("file"),
        location_line=location.get("line"),
        evidence_id=str(evidence_id) if evidence_id is not None else None,
    )


def _stable_key(item: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    return (
        str(item.get("severity") or ""),
        str(item.get("status") or ""),
        str(item.get("rule_id") or ""),
        str(item.get("source_entity_id") or ""),
        str(item.get("target_entity_id") or ""),
    )


def _ordering_key(item: Dict[str, Any]) -> Tuple[Any, ...]:
    source = item.get("source") or {}
    target = item.get("target") or {}
    sev_rank = {"error": 0, "warning": 1, "info": 2}
    stat_rank = {"FAILED": 0, "ERROR": 1, "SKIPPED": 2, "WARNING": 2, "OK": 3}
    return (
        sev_rank.get(str(item.get("severity") or "").lower(), 9),
        stat_rank.get(str(item.get("status") or ""), 9),
        str(item.get("rule_id") or ""),
        str(item.get("source_entity_id") or ""),
        str(item.get("target_entity_id") or ""),
        str(source.get("file") or ""),
        -1 if source.get("line") is None else int(source.get("line") or 0),
        str(target.get("file") or ""),
        -1 if target.get("line") is None else int(target.get("line") or 0),
        str(item.get("result_id") or ""),
    )


def _config_fingerprint(config_snapshot: Optional[Dict[str, Any]]) -> Optional[str]:
    if not config_snapshot:
        return None
    try:
        payload = json.dumps(config_snapshot, sort_keys=True, separators=(",", ":"))
    except TypeError:
        payload = json.dumps(
            config_snapshot, sort_keys=True, default=str, separators=(",", ":")
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _result_item(item: Dict[str, Any]) -> ResultItem:
    known_keys = {
        "result_id",
        "project_id",
        "rule_id",
        "rule_type",
        "category",
        "status",
        "severity",
        "message",
        "source_entity_id",
        "target_entity_id",
        "match_status",
        "confidence",
        "source",
        "target",
        "evidence",
        "details",
        "fix_hints",
        "tags",
        "timing_seconds",
        "activation_source",
    }
    return ResultItem(
        result_id=str(item.get("result_id") or ""),
        project_id=str(item.get("project_id") or ""),
        rule_id=str(item.get("rule_id") or ""),
        rule_type=(
            str(item["rule_type"]) if item.get("rule_type") is not None else None
        ),
        category=str(item.get("category") or ""),
        status=str(item.get("status") or ""),
        severity=str(item.get("severity") or ""),
        message=str(item.get("message") or ""),
        source_entity_id=(
            str(item["source_entity_id"])
            if item.get("source_entity_id") is not None
            else None
        ),
        target_entity_id=(
            str(item["target_entity_id"])
            if item.get("target_entity_id") is not None
            else None
        ),
        match_status=(
            str(item["match_status"]) if item.get("match_status") is not None else None
        ),
        confidence=(
            float(item["confidence"]) if item.get("confidence") is not None else None
        ),
        source=_entity_ref(item.get("source") or {}),
        target=_entity_ref(item.get("target") or {}),
        evidence=tuple(_evidence_item(ev) for ev in (item.get("evidence") or [])),
        details=dict(item.get("details") or {}),
        fix_hints=tuple(str(v) for v in (item.get("fix_hints") or [])),
        tags=tuple(str(v) for v in (item.get("tags") or [])),
        timing_seconds=(
            float(item["timing_seconds"])
            if item.get("timing_seconds") is not None
            else None
        ),
        activation_source=(
            str(item["activation_source"])
            if item.get("activation_source") is not None
            else None
        ),
        stable_key=_stable_key(item),
        ordering_key=_ordering_key(item),
        extras={k: v for k, v in item.items() if k not in known_keys},
    )


def _matching_summary(matches: Iterable[Dict[str, Any]]) -> MatchingSummary:
    rows = list(matches)
    summary = {
        "total": len(rows),
        "matched": 0,
        "low_confidence": 0,
        "ambiguous": 0,
        "unmatched": 0,
    }
    for row in rows:
        status = str(row.get("status") or "")
        if status in summary:
            summary[status] += 1
    return MatchingSummary(
        total=summary["total"],
        matched=summary["matched"],
        low_confidence=summary["low_confidence"],
        ambiguous=summary["ambiguous"],
        unmatched=summary["unmatched"],
    )


def _results_summary(payload: Optional[Dict[str, Any]]) -> ResultsSummary:
    data = payload or {}
    return ResultsSummary(
        results_total=int(data.get("results_total", 0)),
        status_counts=dict(data.get("status_counts") or {}),
        severity_counts=dict(data.get("severity_counts") or {}),
        category_counts=dict(data.get("category_counts") or {}),
        top_rules=tuple(dict(row) for row in (data.get("top_rules") or [])),
        top_source_files=tuple(
            dict(row) for row in (data.get("top_source_files") or [])
        ),
        timings=(dict(data["timings"]) if data.get("timings") is not None else None),
    )


def _single_target_id(
    run_payload: Dict[str, Any], results: List[Dict[str, Any]]
) -> str:
    if results and results[0].get("project_id"):
        return str(results[0].get("project_id"))
    target_path = run_payload.get("target_path")
    if target_path:
        return Path(str(target_path)).name or "single"
    return "single"


def report_dict_to_ir(report: Dict[str, Any], kind: str) -> ReportDocument:
    """Convert a schema-v2 legacy dict into a typed report document."""
    if kind not in {"single", "multi"}:
        raise ValueError(f"Unsupported report kind: {kind}")

    run_payload = dict(report.get("run") or {})
    generated_at = str(
        report.get("generated_at") or run_payload.get("generated_at") or ""
    )
    schema_version = str(report.get("schema_version") or "2")
    framework_version = str(report.get("framework_version") or "unknown")

    run_meta = RunMeta(
        generated_at=generated_at,
        target_path=(
            str(run_payload["target_path"])
            if run_payload.get("target_path") is not None
            else None
        ),
        source_path=(
            str(run_payload["source_path"])
            if run_payload.get("source_path") is not None
            else None
        ),
        reference_modules=tuple(
            str(v) for v in (run_payload.get("reference_modules") or [])
        ),
        config_snapshot=(
            dict(run_payload["config_snapshot"])
            if run_payload.get("config_snapshot") is not None
            else None
        ),
        config_fingerprint=_config_fingerprint(run_payload.get("config_snapshot")),
        tool_version=framework_version,
        mode=str(run_payload.get("mode") or "static-only"),
    )

    if kind == "single":
        result_payload = [dict(v) for v in (report.get("results") or [])]
        results_ir = sort_results([_result_item(item) for item in result_payload])
        matching_payload = dict(report.get("matching") or {})
        matches = tuple(
            sort_matches(dict(v) for v in (matching_payload.get("matches") or []))
        )
        summary_payload = dict(report.get("summary") or {})
        if not summary_payload and result_payload:
            summary_payload = build_results_summary(result_payload)

        target = TargetReport(
            target_id=_single_target_id(run_payload, result_payload),
            display_name=_single_target_id(run_payload, result_payload),
            source_root=run_meta.source_path,
            target_path=str(run_payload.get("target_path") or ""),
            tags=tuple(),
            mode=str(run_payload.get("mode") or "static-only"),
            matching=MatchingSection(
                matches=matches,
                matching_config=dict(matching_payload.get("matching_config") or {}),
                summary=_matching_summary(matches),
            ),
            results=tuple(results_ir),
            summary=_results_summary(summary_payload),
            artifacts=tuple(),
            exit_code=int(report.get("exit_code", 0)),
        )
        aggregate = AggregateSummary(
            targets_total=1,
            targets_failed=1 if int(report.get("exit_code", 0)) else 0,
            targets_passed=0 if int(report.get("exit_code", 0)) else 1,
            results=_results_summary(summary_payload),
        )
        return ReportDocument(
            schema_version=schema_version,
            framework_version=framework_version,
            generated_at=generated_at,
            run=run_meta,
            targets=(target,),
            summary=aggregate,
            exit_code=int(report.get("exit_code", 0)),
            kind="single",
        )

    target_payloads = [dict(payload or {}) for payload in (report.get("targets") or [])]
    normalized_ids = normalize_target_ids(target_payloads)
    targets: List[TargetReport] = []
    for target_payload in target_payloads:
        results_payload = [dict(v) for v in (target_payload.get("results") or [])]
        results_ir = sort_results([_result_item(item) for item in results_payload])
        matching_payload = dict(target_payload.get("matching") or {})
        matches = tuple(
            sort_matches(dict(v) for v in (matching_payload.get("matches") or []))
        )
        summary_payload = dict(target_payload.get("summary") or {})
        if not summary_payload and results_payload:
            summary_payload = build_results_summary(results_payload)
        original_target_id = str(target_payload.get("target_id") or "")
        display_name_override = str(
            target_payload.get("display_name") or original_target_id
        )
        target_path = str(target_payload.get("target_path") or "")
        canonical_target_id, display_name = normalized_ids.get(
            (original_target_id, target_path),
            (slugify_target_id(original_target_id), display_name_override),
        )
        display_name = display_name_override or display_name
        targets.append(
            TargetReport(
                target_id=canonical_target_id,
                display_name=display_name,
                source_root=run_meta.source_path,
                target_path=target_path,
                tags=tuple(str(v) for v in (target_payload.get("tags") or [])),
                mode=str(target_payload.get("mode") or run_meta.mode),
                matching=MatchingSection(
                    matches=matches,
                    matching_config=dict(matching_payload.get("matching_config") or {}),
                    summary=_matching_summary(matches),
                ),
                results=tuple(results_ir),
                summary=_results_summary(summary_payload),
                artifacts=tuple(
                    dict(v) for v in (target_payload.get("artifacts") or [])
                ),
                exit_code=int(target_payload.get("exit_code", 0)),
            )
        )
    targets = sort_targets(targets)

    summary_payload = dict(report.get("summary") or {})
    results_summary_payload = dict(summary_payload.get("results") or {})
    aggregate = AggregateSummary(
        targets_total=int(summary_payload.get("targets_total", len(targets))),
        targets_failed=int(summary_payload.get("targets_failed", 0)),
        targets_passed=int(summary_payload.get("targets_passed", 0)),
        results=_results_summary(results_summary_payload),
    )

    return ReportDocument(
        schema_version=schema_version,
        framework_version=framework_version,
        generated_at=generated_at,
        run=run_meta,
        targets=tuple(targets),
        summary=aggregate,
        exit_code=int(report.get("exit_code", 0)),
        kind="multi",
    )
