"""Proposed cases of a reference entity, run and judged.

The cases are accepted when every case could be set up and run (an exception
the reference raises on purpose is fine and reported) and the lines of the
entity that the cases ran are at least ``min_coverage`` of all its lines. The
calls between modules they drove are returned too: that is what a runtime
check built on these cases will see.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

DEFAULT_MIN_COVERAGE = 0.8


def judge_cases(
    source_path: Path,
    entity: Any,
    entry: str,
    cases: list[dict[str, Any]],
    init: Optional[dict[str, Any]],
    min_coverage: float,
    timeout_s: float,
    policy: Any,
) -> dict[str, Any]:
    """Run ``cases`` of the reference ``entity`` (named ``entry``) and judge
    them (module docstring)."""
    from pythonarchtesting.dynamic.runner import run_cases
    from pythonarchtesting.execution.evaluators.runtime_structure import (
        case_coverage,
        case_edges,
    )

    outcome = run_cases(
        target_root=source_path,
        module_path=entity.module_path,
        qualname=entity.qualname,
        kind=entity.kind,
        cases=cases,
        init=init,
        timeout_s=float(timeout_s),
        sandbox=policy,
        observe={"calls": "edges"},
    )
    reasons: list[str] = []
    if outcome.status != "completed":
        reasons.append(f"the reference did not run: {outcome.status}: {outcome.error}")
    reported = [
        {
            "index": case.get("index"),
            "status": case.get("status"),
            "failures": list(case.get("failures") or []),
            **({"raised": case["raised"]} if case.get("raised") else {}),
        }
        for case in outcome.cases
    ]
    for case in reported:
        if case["status"] == "error":
            reasons.append(f"case {case['index']} could not run: {case['failures']}")
    coverage = case_coverage(list(outcome.cases))
    if coverage is not None:
        total = coverage["lines_total"]
        coverage["ratio"] = round(coverage["lines_run"] / total, 3) if total else 1.0
        if coverage["ratio"] < float(min_coverage):
            reasons.append(
                f"coverage {coverage['ratio']:.0%} of {entry} is below "
                f"{float(min_coverage):.0%}; add cases for lines "
                f"{coverage['unexercised_lines']}"
            )
    edges = sorted(
        {f"{a} -> {b}" for case in outcome.cases for a, b in case_edges(case)}
    )
    result: dict[str, Any] = {
        "accepted": not reasons,
        "reasons": reasons,
        "entry": entry,
        "probe_status": outcome.status,
        "cases": reported,
        "coverage": coverage,
        "edges": edges,
    }
    if outcome.stderr and reasons:
        result["stderr_tail"] = outcome.stderr
    return result


__all__ = ["DEFAULT_MIN_COVERAGE", "judge_cases"]
