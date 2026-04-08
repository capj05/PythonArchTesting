"""Renderer-only matching debug helpers for Markdown outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .table import Table, render_markdown_table

DEFAULT_MATCHING_DEBUG_TOP_K = 10
_PREFERRED_METRIC_ORDER = ("ast", "mod", "name", "doc", "penalty", "module_distance")
_ANCHOR_RE = re.compile(r"[^a-zA-Z0-9._-]+")


@dataclass(frozen=True, slots=True)
class MatchingDebugIdentity:
    id: str
    name: str
    type: str
    location: Optional[str]


@dataclass(frozen=True, slots=True)
class MatchingDebugCandidate:
    target: MatchingDebugIdentity
    confidence_overall: Optional[float]
    confidence_metrics: Dict[str, float]
    explanation: Optional[str]


@dataclass(frozen=True, slots=True)
class MatchingDebugSourceBlock:
    source: MatchingDebugIdentity
    match_status: str
    matched_target: Optional[MatchingDebugIdentity]
    matched_confidence: Optional[float]
    candidates_total: int
    candidates_shown: Tuple[MatchingDebugCandidate, ...]
    hidden_candidates: int
    metric_columns: Tuple[str, ...]


def _identity_from_entity(entity: Any) -> Optional[Dict[str, str]]:
    if entity is None:
        return None
    entity_id = getattr(entity, "canonical_id", None)
    if entity_id is None:
        return None
    qualname = getattr(entity, "qualname", None)
    name = getattr(entity, "name", None)
    kind = getattr(entity, "kind", None)
    file_value = getattr(entity, "filepath_rel", None)
    line_value = getattr(entity, "lineno", None)
    location = None
    if file_value:
        location = (
            f"{file_value}:{line_value}" if line_value is not None else str(file_value)
        )
    return {
        "id": str(entity_id),
        "name": str(qualname or name or entity_id),
        "type": str(kind or ""),
        "location": location or "",
    }


def _identity_from_map(
    identity_map: Dict[str, Any], entity_id: Optional[str]
) -> Optional[MatchingDebugIdentity]:
    if not entity_id:
        return None
    raw = identity_map.get(entity_id)
    if not isinstance(raw, dict):
        return None
    return MatchingDebugIdentity(
        id=str(raw.get("id") or entity_id),
        name=str(raw.get("name") or entity_id),
        type=str(raw.get("type") or ""),
        location=(str(raw["location"]) if raw.get("location") else None),
    )


def _fallback_identity(entity_id: Optional[str], *, kind: str) -> MatchingDebugIdentity:
    value = str(entity_id or "")
    return MatchingDebugIdentity(
        id=value, name=value or "unknown", type=kind, location=None
    )


def build_single_matching_debug_context(state_obj: Any) -> Dict[str, Any]:
    source_by_id = getattr(state_obj, "source_by_id", {}) or {}
    target_by_id = getattr(state_obj, "target_by_id", {}) or {}
    return {
        "kind": "single",
        "targets": {
            "__single__": {
                "sources": {
                    str(key): value
                    for key, value in (
                        (str(k), _identity_from_entity(v))
                        for k, v in source_by_id.items()
                    )
                    if value is not None
                },
                "targets": {
                    str(key): value
                    for key, value in (
                        (str(k), _identity_from_entity(v))
                        for k, v in target_by_id.items()
                    )
                    if value is not None
                },
            }
        },
    }


def build_multi_matching_debug_context(
    run_state: Any, target_states: Sequence[Any]
) -> Dict[str, Any]:
    source_by_id = getattr(run_state, "source_by_id", {}) or {}
    source_map = {
        str(key): value
        for key, value in (
            (str(k), _identity_from_entity(v)) for k, v in source_by_id.items()
        )
        if value is not None
    }
    targets_ctx: Dict[Any, Any] = {}
    for target_state in target_states:
        target_id = str(getattr(target_state, "target_id", "") or "")
        target_path = str(getattr(target_state, "target_path", "") or "")
        target_by_id = getattr(target_state, "target_by_id", {}) or {}
        targets_ctx[(target_id, target_path)] = {
            "sources": dict(source_map),
            "targets": {
                str(key): value
                for key, value in (
                    (str(k), _identity_from_entity(v)) for k, v in target_by_id.items()
                )
                if value is not None
            },
        }
    return {"kind": "multi", "targets": targets_ctx}


def get_target_debug_context(
    matching_debug_context: Optional[Dict[str, Any]],
    target_report: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not isinstance(matching_debug_context, dict):
        return None
    targets = matching_debug_context.get("targets")
    if not isinstance(targets, dict):
        return None
    if matching_debug_context.get("kind") == "single":
        ctx = targets.get("__single__")
        return ctx if isinstance(ctx, dict) else None

    display_name = str(
        target_report.get("display_name") or target_report.get("target_id") or ""
    )
    target_path = str(target_report.get("target_path") or "")
    ctx = targets.get((display_name, target_path))
    return ctx if isinstance(ctx, dict) else None


def _metric_columns(candidates: Sequence[MatchingDebugCandidate]) -> Tuple[str, ...]:
    keys: set[str] = set()
    for candidate in candidates:
        keys.update(str(k) for k in candidate.confidence_metrics.keys())
    ordered: List[str] = [name for name in _PREFERRED_METRIC_ORDER if name in keys]
    ordered.extend(sorted(k for k in keys if k not in set(_PREFERRED_METRIC_ORDER)))
    return tuple(ordered)


def _candidate_sort_key(candidate: MatchingDebugCandidate) -> Tuple[Any, ...]:
    raw = candidate.confidence_overall
    try:
        conf = float(raw) if raw is not None else float("-inf")
    except (TypeError, ValueError):
        conf = float("-inf")
    return (-conf, candidate.target.id, candidate.target.name)


def _source_sort_key(block: MatchingDebugSourceBlock) -> Tuple[str, str, str]:
    return (block.source.type, block.source.name, block.source.id)


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _display_metric_value(metric_name: str, value: float) -> float:
    if metric_name != "module_distance":
        return value
    # Keep raw distance in matching data; invert only for debug display.
    if value < 0.0:
        return 0.0
    return 1.0 / (1.0 + value)


def _normalize_explanation(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value
    elif isinstance(value, (list, tuple)):
        parts = [str(v).strip() for v in value if str(v).strip()]
        text = "; ".join(parts)
    elif isinstance(value, dict):
        items = []
        for key in sorted(value.keys(), key=str):
            raw = value[key]
            if raw is None:
                continue
            sval = str(raw).strip()
            if sval:
                items.append(f"{key}={sval}")
        text = "; ".join(items)
    else:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def build_matching_debug_blocks_for_target(
    target_report: Dict[str, Any],
    target_ctx: Optional[Dict[str, Any]],
    *,
    top_k: int = DEFAULT_MATCHING_DEBUG_TOP_K,
) -> List[MatchingDebugSourceBlock]:
    matching = target_report.get("matching") or {}
    matches = list(matching.get("matches") or [])
    source_map = (target_ctx or {}).get("sources") or {}
    target_map = (target_ctx or {}).get("targets") or {}

    blocks: List[MatchingDebugSourceBlock] = []
    for match in matches:
        source_id = str(match.get("source_entity_id") or "")
        source_identity = _identity_from_map(
            source_map, source_id
        ) or _fallback_identity(source_id, kind="source")
        selected_target_id = (
            str(match.get("target_entity_id"))
            if match.get("target_entity_id") is not None
            else None
        )
        selected_identity = _identity_from_map(target_map, selected_target_id)
        if selected_target_id and selected_identity is None:
            selected_identity = _fallback_identity(selected_target_id, kind="target")

        candidates_raw = list(match.get("candidates") or [])
        candidates: List[MatchingDebugCandidate] = []
        for candidate in candidates_raw:
            candidate_target_id = (
                str(candidate.get("target_entity_id"))
                if candidate.get("target_entity_id") is not None
                else None
            )
            target_identity = _identity_from_map(target_map, candidate_target_id)
            if target_identity is None:
                target_identity = _fallback_identity(candidate_target_id, kind="target")
            metrics_raw = candidate.get("breakdown") or {}
            metrics: Dict[str, float] = {}
            if isinstance(metrics_raw, dict):
                for key, value in metrics_raw.items():
                    fv = _to_float(value)
                    if fv is not None:
                        metric_name = str(key)
                        metrics[metric_name] = _display_metric_value(metric_name, fv)
            candidates.append(
                MatchingDebugCandidate(
                    target=target_identity,
                    confidence_overall=_to_float(candidate.get("confidence")),
                    confidence_metrics=metrics,
                    explanation=_normalize_explanation(candidate.get("explanations")),
                )
            )

        candidates_sorted = sorted(candidates, key=_candidate_sort_key)
        shown = tuple(candidates_sorted[: max(0, top_k)])
        hidden = max(0, len(candidates_sorted) - len(shown))
        blocks.append(
            MatchingDebugSourceBlock(
                source=source_identity,
                match_status=str(match.get("status") or ""),
                matched_target=selected_identity,
                matched_confidence=_to_float(match.get("confidence")),
                candidates_total=len(candidates_sorted),
                candidates_shown=shown,
                hidden_candidates=hidden,
                metric_columns=_metric_columns(shown),
            )
        )

    return sorted(blocks, key=_source_sort_key)


def format_matching_identity(
    identity: Optional[Dict[str, Any]] | MatchingDebugIdentity,
    fallback_id: Optional[str],
) -> str:
    if isinstance(identity, MatchingDebugIdentity):
        item = identity
    elif isinstance(identity, dict):
        item = MatchingDebugIdentity(
            id=str(identity.get("id") or (fallback_id or "")),
            name=str(identity.get("name") or (fallback_id or "unknown")),
            type=str(identity.get("type") or ""),
            location=(str(identity["location"]) if identity.get("location") else None),
        )
    else:
        item = _fallback_identity(fallback_id, kind="")
    base = f"{item.name} [{item.type or 'unknown'}] ({item.id})"
    if item.location:
        return f"{base} @ {item.location}"
    return base


def _format_confidence(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    text = f"{float(value):.6f}"
    text = text.rstrip("0").rstrip(".")
    return text if text else "0"


def _anchor_for_source_id(source_id: str) -> str:
    slug = _ANCHOR_RE.sub("-", source_id).strip("-").lower()
    return slug or "source"


def _escape_markdown_debug(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("|", "\\|")
        .replace("\n", " ")
    )


def collect_metric_columns(candidates: Sequence[MatchingDebugCandidate]) -> List[str]:
    return list(_metric_columns(candidates))


def compute_metric_normalization(
    candidates: Sequence[MatchingDebugCandidate],
    columns: Sequence[str],
) -> Dict[str, Dict[str, Any]]:
    norms: Dict[str, Dict[str, Any]] = {}
    for column in columns:
        values = [
            candidate.confidence_metrics[column]
            for candidate in candidates
            if column in candidate.confidence_metrics
        ]
        if not values:
            norms[column] = {"mode": "none", "min": None, "max": None}
            continue
        min_value = min(values)
        max_value = max(values)
        in_zero_one = all(0.0 <= v <= 1.0 for v in values)
        if in_zero_one:
            norms[column] = {"mode": "direct", "min": 0.0, "max": 1.0}
        elif max_value == min_value:
            norms[column] = {"mode": "constant", "min": min_value, "max": max_value}
        else:
            norms[column] = {"mode": "minmax", "min": min_value, "max": max_value}
    return norms


def _normalized_intensity(value: float, norm: Dict[str, Any]) -> float:
    mode = norm.get("mode")
    if mode == "direct":
        return max(0.0, min(1.0, value))
    if mode == "minmax":
        min_value = float(norm.get("min", 0.0))
        max_value = float(norm.get("max", 1.0))
        span = max_value - min_value
        if span <= 0:
            return 0.15
        return max(0.0, min(1.0, (value - min_value) / span))
    if mode == "constant":
        return 0.15
    return 0.0


def render_matching_debug_markdown(
    blocks: Sequence[MatchingDebugSourceBlock],
    *,
    top_k: int = DEFAULT_MATCHING_DEBUG_TOP_K,
    heading_level: int = 2,
) -> str:
    heading_marks = "#" * max(1, heading_level)
    source_heading_marks = "#" * max(1, min(6, heading_level + 1))
    if not blocks:
        return (
            f"{heading_marks} Matching Candidates (Debug)\n\n"
            "No matching data available.\n"
        )

    lines: List[str] = [
        f"{heading_marks} Matching Candidates (Debug)",
        "",
        f"Showing top {top_k} candidates per source object.",
        "",
    ]
    for block in blocks:
        lines.append(f"{source_heading_marks} Source: {
            _escape_markdown_debug(
                block.source.name)}")
        lines.append("")
        lines.append(
            "- Source: "
            + _escape_markdown_debug(
                format_matching_identity(block.source, block.source.id)
            )
        )
        lines.append(f"- Match status: `{_escape_markdown_debug(block.match_status)}`")
        selected = (
            _escape_markdown_debug(format_matching_identity(block.matched_target, None))
            if block.matched_target is not None
            else "N/A"
        )
        lines.append(f"- Selected match: {selected}")
        lines.append(
            f"- Overall confidence: {_format_confidence(block.matched_confidence)}"
        )
        lines.append("")
        lines.append(
            f"Candidates ({len(block.candidates_shown)}/{block.candidates_total}):"
        )
        lines.append("")
        if not block.candidates_total:
            lines.append("No candidates recorded.")
            lines.append("")
            continue
        rows: List[Tuple[str, str, str, str]] = []
        for idx, candidate in enumerate(block.candidates_shown, start=1):
            rows.append(
                (
                    str(idx),
                    format_matching_identity(candidate.target, candidate.target.id),
                    _format_confidence(candidate.confidence_overall),
                    candidate.explanation or "",
                )
            )
        lines.append(
            render_markdown_table(
                Table(
                    headers=("#", "Candidate", "Overall", "Explanation"),
                    rows=tuple(rows),
                )
            )
        )
        lines.append("")
        if block.hidden_candidates:
            lines.append(f"+{block.hidden_candidates} more not shown (limit {top_k}).")
            lines.append("")
        if block.metric_columns:
            if len(block.metric_columns) <= 6:
                metric_rows: List[Tuple[str, ...]] = []
                headers = ("Candidate", "Overall", *block.metric_columns)
                for candidate in block.candidates_shown:
                    metric_rows.append(
                        (
                            candidate.target.name,
                            _format_confidence(candidate.confidence_overall),
                            *[
                                (
                                    _format_confidence(
                                        candidate.confidence_metrics.get(col)
                                    )
                                    if col in candidate.confidence_metrics
                                    else ""
                                )
                                for col in block.metric_columns
                            ],
                        )
                    )
                lines.append("Metric breakdown:")
                lines.append("")
                lines.append(
                    render_markdown_table(
                        Table(headers=headers, rows=tuple(metric_rows))
                    )
                )
                lines.append("")
            else:
                lines.append("Metric breakdown:")
                lines.append(
                    "- Metric heatmap omitted in Markdown output "
                    f"({len(block.metric_columns)} metrics omitted in Markdown)."
                )
                lines.append("")
    return "\n".join(lines)
