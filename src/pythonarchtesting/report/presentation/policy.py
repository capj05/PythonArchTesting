"""Pure policy helpers for deriving presentation display state."""

from __future__ import annotations

from typing import Iterable, Sequence

from ..ir.models import ReportDocument, ResultItem, TargetReport
from .models import DisplayStatus, MarkdownMode, MatchingVisibility, TargetPresentation


def derive_target_display_status(target: TargetReport) -> DisplayStatus:
    """Derive target presentation status from target IR only."""
    statuses = {item.status for item in target.results}
    if "ERROR" in statuses:
        return "ERROR"
    if "FAILED" in statuses or target.exit_code == 1:
        return "ISSUES"
    if "WARNING" in statuses or "SKIPPED" in statuses:
        return "WARNINGS ONLY"
    return "OK"


def derive_run_display_status(
    document: ReportDocument, targets: Sequence[TargetPresentation]
) -> DisplayStatus:
    """Derive run presentation status from target presentations and exit code."""
    statuses = {target.display_status for target in targets}
    if "ERROR" in statuses:
        return "ERROR"
    if "ISSUES" in statuses or document.exit_code == 1:
        return "ISSUES"
    if "WARNINGS ONLY" in statuses:
        return "WARNINGS ONLY"
    return "OK"


def derive_matching_visibility(
    target: TargetReport,
    *,
    mode: MarkdownMode,
    visible_groups: Iterable[object],
) -> tuple[MatchingVisibility, str | None]:
    """Derive mode-aware matching visibility and the reason for it."""
    if mode == "standard":
        return "hidden", None

    summary = target.matching.summary
    if mode == "debug":
        if summary.total > 0:
            return "debug_only", "matching data available for debug appendices"
        return "hidden", None

    if any(getattr(group, "show_matching_context", False) for group in visible_groups):
        return "contextual", "visible result groups require matching context"
    if summary.low_confidence > 0 or summary.ambiguous > 0 or summary.unmatched > 0:
        return "summary_only", "matching summary explains uncertainty"
    return "hidden", None


def group_has_matching_context(items: Iterable[ResultItem]) -> bool:
    """Return whether a visible result group needs matching explanation."""
    for item in items:
        if item.status == "SKIPPED":
            return True
        if item.match_status not in {None, "", "matched"}:
            return True
    return False
