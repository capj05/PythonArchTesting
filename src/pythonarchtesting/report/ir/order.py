"""Deterministic ordering helpers for IR content."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple, TypeVar

from .models import ResultItem, TargetReport

SEV_RANK = {"error": 0, "warning": 1, "info": 2}
STAT_RANK = {"FAILED": 0, "ERROR": 1, "SKIPPED": 2, "WARNING": 2, "OK": 3}

T = TypeVar("T")


def sort_targets(targets: Sequence[TargetReport]) -> List[TargetReport]:
    """Sort targets deterministically by target id."""
    return sorted(
        targets,
        key=lambda t: (t.target_id, str(Path(t.target_path)) if t.target_path else ""),
    )


def sort_results(items: Sequence[ResultItem]) -> List[ResultItem]:
    """Sort result items deterministically."""
    return sorted(
        items,
        key=lambda r: r.ordering_key,
    )


def sort_evidence(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort evidence dictionaries deterministically."""

    def _key(ev: Dict[str, Any]) -> Tuple[Any, ...]:
        loc = ev.get("location") or {}
        file_value = loc.get("file")
        line_value = loc.get("line")
        return (
            ev.get("type", ""),
            file_value is None,
            file_value or "",
            line_value is None,
            line_value if line_value is not None else 0,
            repr(ev.get("payload", {})),
        )

    return sorted(list(items), key=_key)


def sort_matches(matches: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort matching rows by source entity id."""
    return sorted(
        matches,
        key=lambda m: (
            str(m.get("source_entity_id") or ""),
            str(m.get("status") or ""),
            str(m.get("target_entity_id") or ""),
        ),
    )


def sort_candidates(candidates: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort candidate rows by confidence then tie-break fields."""

    def _key(candidate: Dict[str, Any]) -> Tuple[Any, ...]:
        breakdown = candidate.get("breakdown") or {}
        module_distance = breakdown.get("module_distance", 10**9)
        confidence_raw = candidate.get("confidence")
        try:
            confidence = float(confidence_raw) if confidence_raw is not None else 0.0
        except (TypeError, ValueError):
            confidence = 0.0
        return (-confidence, module_distance, candidate.get("target_entity_id") or "")

    return sorted(candidates, key=_key)


def sort_artifacts(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort artifact rows deterministically."""
    return sorted(
        list(items),
        key=lambda a: (
            str(a.get("type") or a.get("artifact_type") or ""),
            str(a.get("path") or ""),
            str(a.get("name") or ""),
        ),
    )
