"""Shared renderer helpers for deterministic output across formats."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


def format_entity(entity: Dict[str, Any]) -> str:
    """Format entity as module:qualname label."""
    module = entity.get("module") or ""
    qualname = entity.get("qualname") or ""
    if module and qualname:
        return f"{module}:{qualname}"
    return module or qualname or ""


def format_location(source: Dict[str, Any]) -> str:
    """Format file:line location from source dictionary."""
    file_value = source.get("file")
    line_value = source.get("line")
    if file_value and line_value is not None:
        return f"{file_value}:{line_value}"
    if file_value:
        return str(file_value)
    return ""


def summarize_matching(matching: Dict[str, Any]) -> Dict[str, int]:
    """Compute status counts for matching section."""
    matches = matching.get("matches", []) or []
    summary_counts = {
        "total": len(matches),
        "matched": 0,
        "low_confidence": 0,
        "ambiguous": 0,
        "unmatched": 0,
    }
    for match in matches:
        status = str(match.get("status", ""))
        if status in summary_counts:
            summary_counts[status] += 1
    return summary_counts


def format_payload(payload: Any) -> str:
    """Serialize payload for text display."""
    try:
        return json.dumps(payload, sort_keys=True)
    except TypeError:
        return repr(payload)


def format_evidence(ev: Dict[str, Any]) -> str:
    """Render one evidence row for text-like outputs."""
    loc = ev.get("location") or {}
    file_value = loc.get("file")
    line_value = loc.get("line")
    if file_value:
        if line_value is not None:
            loc_text = f"{file_value}:{line_value}"
        else:
            loc_text = file_value
    else:
        loc_text = "unknown"
    payload = ev.get("payload", {})
    line_text = None
    if isinstance(payload, dict) and "line_text" in payload:
        payload = dict(payload)
        line_text = payload.pop("line_text")
    rendered = f"{
        ev.get(
            'type',
            '')} at {loc_text} ({
            format_payload(payload)})"
    if isinstance(line_text, str) and line_text.strip():
        rendered += f" line={line_text.strip()!r}"
    return rendered


def split_results_by_severity(
    results: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split result rows into error/warning/info buckets."""
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    info: List[Dict[str, Any]] = []
    for item in results:
        status = item.get("status")
        severity = item.get("severity")
        if status in ("FAILED", "ERROR"):
            errors.append(item)
        elif status in ("WARNING", "SKIPPED"):
            warnings.append(item)
        elif severity == "error":
            errors.append(item)
        elif severity == "warning":
            warnings.append(item)
        else:
            info.append(item)
    return errors, warnings, info


def core_rows(
    results: List[Dict[str, Any]],
) -> List[Tuple[str, str, str, str, str, str]]:
    """Projection used by parity tests across output formats."""
    rows: List[Tuple[str, str, str, str, str, str]] = []
    for item in results:
        rows.append(
            (
                str(item.get("project_id") or ""),
                str(item.get("result_id") or ""),
                str(item.get("rule_id") or ""),
                str(item.get("category") or ""),
                str(item.get("severity") or ""),
                str(item.get("status") or ""),
            )
        )
    return rows
