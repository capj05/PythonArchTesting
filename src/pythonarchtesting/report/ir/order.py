"""Deterministic ordering helpers for IR content."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, TypeVar

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
