"""Pure builders that adapt canonical report IR into presentation models."""

from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Sequence, Tuple

from ..ir.models import (
    EntityRef,
    ReportDocument,
    ResultItem,
    ResultsSummary,
    TargetReport,
)
from .models import (
    CompactPassedSummary,
    DisplayStatus,
    MarkdownMode,
    MatchingPresentation,
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

_GROUP_STATUS_PRIORITY = {"ERROR": 0, "FAILED": 1, "WARNING": 2, "SKIPPED": 3}
_SEVERITY_PRIORITY = {"error": 0, "warning": 1, "info": 2}


def build_run_presentation(
    document: ReportDocument, *, mode: MarkdownMode
) -> RunPresentation:
    """Build a run-level presentation contract from the canonical IR."""
    target_presentations = tuple(
        build_target_presentation(target, mode=mode) for target in document.targets
    )
    has_target_pages = document.kind == "multi" and mode != "standard"
    target_summaries = tuple(
        _build_target_summary_card(
            target, presentation, has_target_pages=has_target_pages
        )
        for target, presentation in zip(document.targets, target_presentations)
    )
    targets_with_issues = tuple(
        card for card in target_summaries if card.display_status == "ISSUES"
    )
    warnings_only_targets = tuple(
        card for card in target_summaries if card.display_status == "WARNINGS ONLY"
    )
    ok_targets = tuple(card for card in target_summaries if card.display_status == "OK")
    error_targets = tuple(
        card for card in target_summaries if card.display_status == "ERROR"
    )
    return RunPresentation(
        title=(
            "Validation Report"
            if document.kind == "single"
            else "Validation Run Report"
        ),
        display_status=derive_run_display_status(document, target_presentations),
        exit_code=document.exit_code,
        targets_total=len(document.targets),
        targets_ok=len(ok_targets),
        targets_issues=len(targets_with_issues),
        targets_warnings_only=len(warnings_only_targets),
        targets_error=len(error_targets),
        rule_hotspots=build_rule_hotspots(document.summary.results, document.targets),
        target_summaries=target_summaries,
        targets_with_issues=targets_with_issues,
        warnings_only_targets=warnings_only_targets,
        ok_targets=ok_targets,
        error_targets=error_targets,
        has_target_pages=has_target_pages,
        mode=mode,
    )


def build_target_presentation(
    target: TargetReport, *, mode: MarkdownMode
) -> TargetPresentation:
    """Build a target-level presentation contract from canonical IR."""
    all_groups = group_results_by_rule(target.results, mode=mode)
    issue_groups = tuple(
        group for group in all_groups if group.display_status in {"ERROR", "ISSUES"}
    )
    warning_groups = tuple(
        group for group in all_groups if group.display_status == "WARNINGS ONLY"
    )
    return TargetPresentation(
        title=f"Target Report: {target.display_name}",
        target_id=target.target_id,
        display_name=target.display_name,
        target_path=target.target_path,
        display_status=derive_target_display_status(target),
        exit_code=target.exit_code,
        issue_groups=issue_groups,
        warning_groups=warning_groups,
        compact_passed_summary=build_compact_passed_summary(target.results),
        matching_summary=build_matching_presentation(
            target, issue_groups, warning_groups, mode=mode
        ),
        debug_sections_allowed=mode == "debug",
        mode=mode,
    )


def group_results_by_rule(
    results: Tuple[ResultItem, ...], *, mode: MarkdownMode
) -> Tuple[RuleIssueGroup, ...]:
    """Group visible non-OK results by rule for reader-facing presentation."""
    del mode
    grouped: Dict[tuple[str, str], List[ResultItem]] = {}
    for item in results:
        if item.status == "OK":
            continue
        if item.status not in {"ERROR", "FAILED", "WARNING", "SKIPPED"}:
            continue
        key = (item.rule_id, item.rule_type or "")
        grouped.setdefault(key, []).append(item)

    return tuple(_build_rule_issue_group(items) for items in grouped.values())


def build_rule_hotspots(
    summary: ResultsSummary, targets: Tuple[TargetReport, ...]
) -> Tuple[RuleHotspot, ...]:
    """Build normalized hotspot entries using summary.top_rules as the primary seed."""
    top_rules = [
        dict(entry)
        for entry in summary.top_rules
        if str(entry.get("name") or "").strip()
    ]
    if not top_rules:
        counts = Counter(
            item.rule_id
            for target in targets
            for item in target.results
            if item.rule_id.strip()
        )
        top_rules = [
            {"name": rule_id, "count": count}
            for rule_id, count in sorted(
                counts.items(), key=lambda item: (-item[1], item[0])
            )
        ]

    hotspots: List[RuleHotspot] = []
    for entry in top_rules:
        rule_id = str(entry.get("name") or "").strip()
        if not rule_id:
            continue
        hotspots.append(
            RuleHotspot(
                rule_id=rule_id,
                count=int(entry.get("count", 0)),
                severity_mix=_severity_mix_for_rule(rule_id, targets),
                targets_affected=sum(
                    1
                    for target in targets
                    if any(item.rule_id == rule_id for item in target.results)
                ),
            )
        )
    return tuple(hotspots)


def build_compact_passed_summary(
    results: Tuple[ResultItem, ...],
) -> CompactPassedSummary:
    """Summarize passing rows without exposing every OK row."""
    passed_results = [item for item in results if item.status == "OK"]
    counts = Counter(item.rule_id for item in passed_results if item.rule_id.strip())
    top_passed_rules = tuple(
        RuleCount(rule_id=rule_id, count=count)
        for rule_id, count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )[:3]
    )
    displayed_total = sum(item.count for item in top_passed_rules)
    return CompactPassedSummary(
        passed_total=len(passed_results),
        top_passed_rules=top_passed_rules,
        hidden_passed_count=max(0, len(passed_results) - displayed_total),
    )


def build_matching_presentation(
    target: TargetReport,
    issue_groups: Sequence[RuleIssueGroup],
    warning_groups: Sequence[RuleIssueGroup],
    *,
    mode: MarkdownMode,
) -> MatchingPresentation:
    """Build mode-aware matching presentation from target IR and visible groups."""
    visibility, reason = derive_matching_visibility(
        target,
        mode=mode,
        visible_groups=tuple(issue_groups) + tuple(warning_groups),
    )
    summary = target.matching.summary
    return MatchingPresentation(
        total=summary.total,
        matched=summary.matched,
        low_confidence=summary.low_confidence,
        ambiguous=summary.ambiguous,
        unmatched=summary.unmatched,
        visibility=visibility,
        reason=reason,
    )


def _build_target_summary_card(
    target: TargetReport,
    presentation: TargetPresentation,
    *,
    has_target_pages: bool,
) -> TargetSummaryCard:
    top_rule_ids = tuple(
        hotspot.rule_id
        for hotspot in build_rule_hotspots(target.summary, (target,))[:3]
    )
    matching_summary = presentation.matching_summary
    issue_count = sum(group.failed_count for group in presentation.issue_groups)
    warning_count = sum(
        group.warning_count + group.skipped_count
        for group in presentation.warning_groups
    )
    return TargetSummaryCard(
        target_id=target.target_id,
        display_name=target.display_name,
        target_path=target.target_path,
        display_status=presentation.display_status,
        exit_code=target.exit_code,
        results_total=target.summary.results_total,
        issue_count=issue_count,
        warning_count=warning_count,
        top_rule_ids=top_rule_ids,
        has_matching_anomalies=(
            matching_summary.low_confidence > 0
            or matching_summary.ambiguous > 0
            or matching_summary.unmatched > 0
        ),
        has_target_page=has_target_pages,
    )


def _build_rule_issue_group(items: Sequence[ResultItem]) -> RuleIssueGroup:
    first = items[0]
    return RuleIssueGroup(
        rule_id=first.rule_id,
        rule_type=first.rule_type,
        display_status=_group_display_status(items),
        severity=_group_severity(items),
        failed_count=sum(item.status in {"ERROR", "FAILED"} for item in items),
        warning_count=sum(item.status == "WARNING" for item in items),
        skipped_count=sum(item.status == "SKIPPED" for item in items),
        summary_message=_summary_message(items),
        items=tuple(_build_rule_issue_item(item) for item in items),
        fix_hints=_dedupe_preserve_order(
            hint for item in items for hint in item.fix_hints if hint.strip()
        ),
        show_matching_context=group_has_matching_context(items),
    )


def _build_rule_issue_item(item: ResultItem) -> RuleIssueItem:
    return RuleIssueItem(
        result_id=item.result_id,
        status=item.status,
        severity=item.severity,
        message=item.message,
        source_display=_format_entity(item.source, fallback="unknown source"),
        target_display=_format_entity(item.target, fallback="unresolved target"),
        location_display=_format_location(item),
        fix_hints=tuple(item.fix_hints),
        match_status=item.match_status,
        has_evidence=bool(item.evidence),
    )


def _group_display_status(items: Sequence[ResultItem]) -> DisplayStatus:
    statuses = {item.status for item in items}
    if "ERROR" in statuses:
        return "ERROR"
    if "FAILED" in statuses:
        return "ISSUES"
    return "WARNINGS ONLY"


def _group_severity(items: Sequence[ResultItem]) -> str:
    return min(
        (item.severity for item in items),
        key=lambda severity: _SEVERITY_PRIORITY.get(severity.lower(), 9),
    )


def _summary_message(items: Sequence[ResultItem]) -> str:
    ranked = sorted(
        items,
        key=lambda item: (
            _GROUP_STATUS_PRIORITY.get(item.status, 9),
            item.ordering_key,
            item.result_id,
        ),
    )
    return ranked[0].message if ranked else ""


def _format_entity(entity: EntityRef, *, fallback: str) -> str:
    parts = [part for part in (entity.module, entity.qualname) if part]
    if parts:
        return ".".join(parts)
    if entity.file:
        return _format_file_line(entity.file, entity.line)
    return fallback


def _format_location(item: ResultItem) -> str:
    source = _format_entity_location(item.source)
    target = _format_entity_location(item.target)
    if source and target and source != target:
        return f"{source} -> {target}"
    if source:
        return source
    if target:
        return target
    return "unknown location"


def _format_entity_location(entity: EntityRef) -> str:
    if entity.file:
        return _format_file_line(entity.file, entity.line)
    return ""


def _format_file_line(path: str, line: int | None) -> str:
    if line is None:
        return path
    return f"{path}:{line}"


def _severity_mix_for_rule(
    rule_id: str, targets: Sequence[TargetReport]
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for target in targets:
        for item in target.results:
            if item.rule_id != rule_id:
                continue
            counts[item.severity] = counts.get(item.severity, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _dedupe_preserve_order(values: Iterable[str]) -> Tuple[str, ...]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)
