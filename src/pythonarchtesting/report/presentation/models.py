"""Reader-oriented presentation models derived from the canonical report IR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Optional, Tuple

MarkdownMode = Literal["standard", "verbose", "debug"]
DisplayStatus = Literal["OK", "ISSUES", "WARNINGS ONLY", "ERROR"]
MatchingVisibility = Literal["hidden", "summary_only", "contextual", "debug_only"]


@dataclass(frozen=True, slots=True)
class RuleCount:
    """Named deterministic count entry used in compact summaries."""

    rule_id: str
    count: int


@dataclass(frozen=True, slots=True)
class RuleIssueItem:
    """Presentation-safe issue row for reader-facing grouping."""

    result_id: str
    status: str
    severity: str
    message: str
    source_display: str
    target_display: str
    location_display: str
    fix_hints: Tuple[str, ...]
    match_status: Optional[str]
    has_evidence: bool


@dataclass(frozen=True, slots=True)
class RuleIssueGroup:
    """Rule-centered presentation block for issues or warnings."""

    rule_id: str
    rule_type: Optional[str]
    display_status: DisplayStatus
    severity: str
    failed_count: int
    warning_count: int
    skipped_count: int
    summary_message: str
    items: Tuple[RuleIssueItem, ...]
    fix_hints: Tuple[str, ...]
    show_matching_context: bool


@dataclass(frozen=True, slots=True)
class RuleHotspot:
    """Run- or target-level recurring rule summary."""

    rule_id: str
    count: int
    severity_mix: Dict[str, int]
    targets_affected: int


@dataclass(frozen=True, slots=True)
class CompactPassedSummary:
    """Compact summary of passing rows without enumerating them all."""

    passed_total: int
    top_passed_rules: Tuple[RuleCount, ...]
    hidden_passed_count: int


@dataclass(frozen=True, slots=True)
class MatchingPresentation:
    """Mode-aware matching visibility summary."""

    total: int
    matched: int
    low_confidence: int
    ambiguous: int
    unmatched: int
    visibility: MatchingVisibility
    reason: Optional[str]


@dataclass(frozen=True, slots=True)
class TargetPresentation:
    """Reader-oriented presentation contract for one target."""

    title: str
    target_id: str
    display_name: str
    target_path: str
    display_status: DisplayStatus
    exit_code: int
    issue_groups: Tuple[RuleIssueGroup, ...]
    warning_groups: Tuple[RuleIssueGroup, ...]
    compact_passed_summary: CompactPassedSummary
    matching_summary: MatchingPresentation
    debug_sections_allowed: bool
    mode: MarkdownMode


@dataclass(frozen=True, slots=True)
class TargetSummaryCard:
    """Run-level compact summary for one target."""

    target_id: str
    display_name: str
    target_path: str
    display_status: DisplayStatus
    exit_code: int
    results_total: int
    issue_count: int
    warning_count: int
    top_rule_ids: Tuple[str, ...]
    has_matching_anomalies: bool
    has_target_page: bool


@dataclass(frozen=True, slots=True)
class RunPresentation:
    """Reader-oriented presentation contract for a full report document."""

    title: str
    display_status: DisplayStatus
    exit_code: int
    targets_total: int
    targets_ok: int
    targets_issues: int
    targets_warnings_only: int
    targets_error: int
    rule_hotspots: Tuple[RuleHotspot, ...]
    target_summaries: Tuple[TargetSummaryCard, ...]
    targets_with_issues: Tuple[TargetSummaryCard, ...]
    warnings_only_targets: Tuple[TargetSummaryCard, ...]
    ok_targets: Tuple[TargetSummaryCard, ...]
    error_targets: Tuple[TargetSummaryCard, ...]
    has_target_pages: bool
    mode: MarkdownMode
