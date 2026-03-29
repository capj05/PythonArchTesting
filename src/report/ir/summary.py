"""Summary helpers for canonical report result sets."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Optional


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def top_counts(values: Iterable[str], limit: int = 5) -> List[Dict[str, Any]]:
    """Return most common values with deterministic tie-breaking."""
    counter = Counter(values)
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [{"name": name, "count": count} for name, count in ranked[:limit]]


def build_results_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build deterministic summary fields from serialized result dictionaries."""
    status_counts: Dict[str, int] = {}
    severity_counts: Dict[str, int] = {}
    for result in results:
        status = str(result.get("status") or "")
        severity = str(result.get("severity") or "")
        status_counts[status] = status_counts.get(status, 0) + 1
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    status_counts = dict(sorted(status_counts.items(), key=lambda kv: kv[0]))
    severity_counts = dict(sorted(severity_counts.items(), key=lambda kv: kv[0]))
    timing_values = [
        timing
        for timing in (_as_float(item.get("timing_seconds")) for item in results)
        if timing is not None
    ]
    timing_summary: Optional[Dict[str, Any]] = None
    if timing_values:
        timing_summary = {
            "count": len(timing_values),
            "total_seconds": round(sum(timing_values), 6),
            "max_seconds": round(max(timing_values), 6),
            "avg_seconds": round(sum(timing_values) / len(timing_values), 6),
        }

    return {
        "results_total": len(results),
        "status_counts": status_counts,
        "severity_counts": severity_counts,
        "category_counts": dict(
            sorted(
                Counter(
                    str(item.get("category") or "unknown") for item in results
                ).items(),
                key=lambda kv: kv[0],
            )
        ),
        "top_rules": top_counts([str(item.get("rule_id") or "") for item in results]),
        "top_source_files": top_counts(
            [
                str((item.get("source") or {}).get("file") or "<unknown>")
                for item in results
            ]
        ),
        "timings": timing_summary,
    }
