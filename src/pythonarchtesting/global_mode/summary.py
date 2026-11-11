"""Several principles of one submission in one report (design § 5.6).

``summarize_outcomes`` keeps each principle's outcome whole and lists the
findings of all of them once more, deduplicated across principles: two
findings of different principles are one when their facts are the same
apart from the fields that only say which run saw them (``case``,
``cases``, ``via``, ``origin_line``), and they name a ``file`` and a
``line``. Such a finding lists every principle it was found under in
``principles``. Two findings of one principle are never merged (the
principle's own classification already merged what is one defect), and a
finding whose facts name no file or line is never merged.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Optional, get_args

from pythonarchtesting.global_mode.model import PrincipleOutcome, Status

# Fields of a fact that say which run saw it, not what happened.
_PER_RUN = frozenset({"case", "cases", "via", "origin_line"})


def _place(finding: Mapping[str, Any]) -> Optional[tuple[Any, ...]]:
    """What makes findings of two principles one (module docstring)."""
    facts = finding.get("facts") or {}
    if facts.get("file") is None or facts.get("line") is None:
        return None
    rest = {k: v for k, v in facts.items() if k not in _PER_RUN}
    return (
        facts["file"],
        facts["line"],
        json.dumps(rest, sort_keys=True, default=str),
    )


def summarize_outcomes(outcomes: Sequence[PrincipleOutcome]) -> dict[str, Any]:
    """The outcomes as one report: ``principles`` (each ``to_dict``),
    ``findings`` (deduplicated across principles, each with ``principles``) and
    ``counts`` (the number of principles per status, every status listed)."""
    findings: list[dict[str, Any]] = []
    by_place: dict[tuple[Any, ...], dict[str, Any]] = {}
    for outcome in outcomes:
        for finding in outcome.findings:
            place = _place(finding)
            known = by_place.get(place) if place is not None else None
            if known is not None and outcome.principle not in known["principles"]:
                known["principles"].append(outcome.principle)
                continue
            entry = {**dict(finding), "principles": [outcome.principle]}
            findings.append(entry)
            if place is not None and known is None:
                by_place[place] = entry
    counts = {status: 0 for status in get_args(Status)}
    for outcome in outcomes:
        counts[outcome.status] += 1
    return {
        "principles": [outcome.to_dict() for outcome in outcomes],
        "findings": findings,
        "counts": counts,
    }


__all__ = ["summarize_outcomes"]
