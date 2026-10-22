"""Counting of runtime rule results a plain pass/fail count would misrepresent.

Results skipped only because runtime checks were disabled, and passes that
left part of the code unchecked.
"""

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


def count_runtime_results_unverified(target_states: Sequence[TargetRunState]) -> int:
    """How many runtime results passed although something was left unchecked.

    Such a pass holds only for the code its cases ran; ``details.unverified``
    names what was left out.
    """
    return sum(
        1
        for state in target_states
        for result in state.rule_results
        if result.status == "OK" and (result.details or {}).get("unverified")
    )
