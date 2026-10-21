"""Counting of rule results skipped only because runtime checks were disabled."""

from __future__ import annotations

from typing import Sequence

from pythonarchtesting.run_state import TargetRunState


def count_runtime_rules_skipped(target_states: Sequence[TargetRunState]) -> int:
    """How many rule results were skipped only because --dynamic was missing."""
    return sum(
        1
        for state in target_states
        for result in state.rule_results
        if result.status == "SKIPPED"
        and (result.details or {}).get("reason") == "dynamic_checks_disabled"
    )
