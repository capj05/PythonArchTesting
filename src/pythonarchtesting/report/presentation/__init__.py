"""Presentation-layer adapters above the canonical reporting IR."""

from .builders import (
    build_compact_passed_summary,
    build_matching_presentation,
    build_rule_hotspots,
    build_run_presentation,
    build_target_presentation,
    group_results_by_rule,
)
from .models import (
    CompactPassedSummary,
    DisplayStatus,
    MarkdownMode,
    MatchingPresentation,
    MatchingVisibility,
    RuleCount,
    RuleHotspot,
    RuleIssueGroup,
    RuleIssueItem,
    RunPresentation,
    TargetPresentation,
    TargetSummaryCard,
)
from .policy import (
    derive_matching_visibility,
    derive_run_display_status,
    derive_target_display_status,
    group_has_matching_context,
)

__all__ = [
    "CompactPassedSummary",
    "DisplayStatus",
    "MarkdownMode",
    "MatchingPresentation",
    "MatchingVisibility",
    "RuleCount",
    "RuleHotspot",
    "RuleIssueGroup",
    "RuleIssueItem",
    "RunPresentation",
    "TargetPresentation",
    "TargetSummaryCard",
    "build_compact_passed_summary",
    "build_matching_presentation",
    "build_rule_hotspots",
    "build_run_presentation",
    "build_target_presentation",
    "derive_matching_visibility",
    "derive_run_display_status",
    "derive_target_display_status",
    "group_has_matching_context",
    "group_results_by_rule",
]
