"""Convert the parts of a serialized schema-v2 report (results, evidence,
entity references, summaries) into typed IR."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple

from .models import (
    EntityRef,
    EvidenceItem,
    MatchingSummary,
    ResultItem,
    ResultsSummary,
)
from .order import SEV_RANK, STAT_RANK


def split_qualname(qualname: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """The class and the function a qualified name ends with (``<locals>``
    left out); ``None`` for a part it does not have."""
    if not qualname:
        return None, None
    parts = [p for p in str(qualname).split(".") if p and p != "<locals>"]
    if not parts:
        return None, None
    if len(parts) == 1:
        return None, parts[0]
    return parts[-2], parts[-1]


def entity_ref(value: Optional[Dict[str, Any]]) -> EntityRef:
    """The typed reference to the entity a serialized ``source``/``target``
    describes."""
    src = value or {}
    cls, function = split_qualname(src.get("qualname"))
    return EntityRef(
        module=src.get("module"),
        qualname=src.get("qualname"),
        file=src.get("file"),
        line=src.get("line"),
        cls=cls,
        function=function,
    )


def evidence_item(value: Dict[str, Any]) -> EvidenceItem:
    """One serialized evidence entry as typed IR; a payload that is no
    mapping is kept under ``value``."""
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
    return (
        SEV_RANK.get(str(item.get("severity") or "").lower(), 9),
        STAT_RANK.get(str(item.get("status") or ""), 9),
        str(item.get("rule_id") or ""),
        str(item.get("source_entity_id") or ""),
        str(item.get("target_entity_id") or ""),
        str(source.get("file") or ""),
        -1 if source.get("line") is None else int(source.get("line") or 0),
        str(target.get("file") or ""),
        -1 if target.get("line") is None else int(target.get("line") or 0),
        str(item.get("result_id") or ""),
    )


def result_item(item: Dict[str, Any]) -> ResultItem:
    """One serialized result as typed IR, with its stable and ordering keys;
    keys the IR has no field for are kept in ``extras``."""
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
        source=entity_ref(item.get("source") or {}),
        target=entity_ref(item.get("target") or {}),
        evidence=tuple(evidence_item(ev) for ev in (item.get("evidence") or [])),
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


def matching_summary(matches: Iterable[Dict[str, Any]]) -> MatchingSummary:
    """How many matches there are in total and per status."""
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


def results_summary(payload: Optional[Dict[str, Any]]) -> ResultsSummary:
    """A serialized results summary (``build_results_summary``) as typed IR."""
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
        unverified_total=int(data.get("unverified_total", 0)),
    )
