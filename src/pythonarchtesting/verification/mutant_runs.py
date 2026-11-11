"""What a mutation check of a marker and of a task share.

A mutant is a copy of the reference with one seeded change. The rule results
of each copy say whether the rule caught it (``mutant_outcome``): *killed*
when the rule fails with a violation, *not_run* when it could not observe
the copy, *survived* when it passes. ``in_turn`` and ``sample_by_operator``
choose the mutants that run under a limit.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

DEFAULT_MAX_MUTANTS = 100
# A rule that ended for one of these reasons observed nothing: not a kill.
_NOT_RUN = ("case_setup_failed", "reference_failed", "target_kind_mismatch")
# What a copy of a reference leaves out.
_IGNORE = shutil.ignore_patterns("__pycache__", ".*")


def rule_matches(rule_id: str, rule: str) -> bool:
    """Whether ``rule_id`` is of ``rule``: a rule id prefix (``"DEP001"``) or
    a marker name (``"forbid_imports"``)."""
    parts = rule_id.split("/")
    return rule_id.startswith(rule) or (len(parts) > 1 and parts[1] == rule)


def did_not_run(result: Any) -> bool:
    """Whether the rule observed nothing: an error, or a failure for one of
    the reasons a probe or case setup gives."""
    reason = str((result.details or {}).get("reason") or "")
    return result.status == "ERROR" or (
        result.status == "FAILED"
        and (reason.startswith("probe_") or reason in _NOT_RUN)
    )


def mutant_outcome(results: list[Any], rule: str) -> tuple[str, list[str], list[str]]:
    """``killed``/``survived``/``not_run`` for one target, failing ids, summaries."""
    matching = [r for r in results if rule_matches(str(r.rule_id), rule)]
    # A part that was SKIPPED by design (runtime without dynamic) says
    # nothing; it matters only when no part of the rule ran at all.
    ours = [r for r in matching if r.status != "SKIPPED"] or matching
    failed = [r for r in ours if r.status == "FAILED" and not did_not_run(r)]
    if failed:
        return (
            "killed",
            sorted({str(r.rule_id) for r in failed}),
            [str((r.details or {}).get("summary") or "") for r in failed][:3],
        )
    broken = [r for r in ours if did_not_run(r) or r.status == "SKIPPED"]
    if broken:
        return (
            "not_run",
            sorted({str(r.rule_id) for r in broken}),
            [str((r.details or {}).get("summary") or "") for r in broken][:3],
        )
    return "survived", [], []


def sample_by_operator(mutants: list[Any], limit: int) -> list[Any]:
    """Up to ``limit`` mutants, taken in turn from each operator."""
    by_operator: dict[str, list[Any]] = {}
    for mutant in mutants:
        by_operator.setdefault(mutant.operator, []).append(mutant)
    return in_turn(list(by_operator.values()), limit)


def in_turn(groups: list[list[Any]], limit: int) -> list[Any]:
    """Up to ``limit`` mutants, taken in turn from each of ``groups``; a
    mutant in several groups (the same ``id``) is taken once, and the group
    whose turn it is takes its next one instead."""
    queues = [list(group) for group in groups]
    chosen: list[Any] = []
    taken: set[str] = set()
    while len(chosen) < limit and any(queues):
        for queue in queues:
            while queue and queue[0].id in taken:
                queue.pop(0)
            if queue and len(chosen) < limit:
                mutant = queue.pop(0)
                taken.add(mutant.id)
                chosen.append(mutant)
    return chosen


def copy_reference(reference: Path, copy: Path) -> None:
    """Copy ``reference`` to ``copy``, without caches and hidden files."""
    shutil.copytree(reference, copy, ignore=_IGNORE)


def write_mutants(
    reference: Path, workdir: Path, mutants: list[Any]
) -> dict[str, Path]:
    """One copy of ``reference`` per mutant, at ``workdir/<mutant id>/<name>``,
    with the mutant's changed files written in; the copies by mutant id."""
    paths: dict[str, Path] = {}
    for mutant in mutants:
        copy = workdir / mutant.id / reference.name
        copy_reference(reference, copy)
        (copy / mutant.file).write_text(mutant.source, encoding="utf-8")
        for other, text in mutant.also:
            (copy / other).write_text(text, encoding="utf-8")
        paths[mutant.id] = copy
    return paths


__all__ = [
    "DEFAULT_MAX_MUTANTS",
    "copy_reference",
    "did_not_run",
    "in_turn",
    "mutant_outcome",
    "rule_matches",
    "sample_by_operator",
    "write_mutants",
]
