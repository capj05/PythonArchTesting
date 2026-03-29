"""Exit-code policy helpers for report generation."""

from __future__ import annotations

from typing import Any, Dict, List

from src.config.accessors import get_bool, get_int, get_str
from src.state_multi import TargetRunState


def compute_exit_code(results: List[Dict[str, Any]], config: Any) -> int:
    """Compute single-target exit code from result rows."""
    warnings_as_fail = get_bool(config, "report", "warnings_as_fail", False)
    for result in results:
        status = result.get("status")
        severity = result.get("severity")
        if status in ("FAILED", "ERROR"):
            return 1
        if status == "SKIPPED":
            continue
        if warnings_as_fail and (severity == "warning" or status == "WARNING"):
            return 1
    return 0


def compute_target_exit_code(  # noqa: E501
    results: List[Dict[str, Any]], config: Any
) -> int:
    """Compute target-level exit code (same policy as single-target)."""
    return compute_exit_code(results, config)


def compute_aggregate_exit_code(
    target_states: List[TargetRunState], config: Any
) -> int:
    """Compute aggregate multi-target exit code using configured policy."""
    policy = get_str(  # noqa: E501
        config, "report", "multi_target_exit_policy", "any_fail"
    ).strip()
    threshold = get_int(config, "report", "fail_threshold", 1)

    failed = sum(1 for t in target_states if t.exit_code == 1)
    total = len(target_states)

    if policy == "all_fail":
        return 1 if total > 0 and failed == total else 0
    if policy == "threshold":
        return 1 if failed >= threshold else 0
    return 1 if failed >= 1 else 0
