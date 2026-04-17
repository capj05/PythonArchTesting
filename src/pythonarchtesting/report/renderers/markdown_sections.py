"""Shared Markdown section builders for mode-aware report renderers."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, Optional, Sequence

from ..ir.models import EntityRef, EvidenceItem, ResultItem, TargetReport
from ..presentation import RuleHotspot, RuleIssueGroup, TargetPresentation
from .common import format_entity, format_location
from .escape import escape_markdown
from .matching_debug import (
    DEFAULT_MATCHING_DEBUG_TOP_K,
    build_matching_debug_blocks_for_target,
    get_target_debug_context,
    render_matching_debug_markdown,
)
from .table import Table, render_markdown_table

_GROUP_STATUS_PRIORITY = {"ERROR": 0, "ISSUES": 1, "WARNINGS ONLY": 2, "OK": 3}
_SEVERITY_PRIORITY = {"error": 0, "warning": 1, "info": 2}


def entity_to_dict(entity: EntityRef) -> Dict[str, Any]:
    """Convert an IR entity reference into the renderer's legacy dict shape."""
    return {
        "module": entity.module,
        "qualname": entity.qualname,
        "file": entity.file,
        "line": entity.line,
    }


def target_debug_report(
    target: TargetReport, *, target_path: Optional[str] = None
) -> Dict[str, Any]:
    """Build the minimal target payload expected by matching debug helpers."""
    return {
        "target_id": target.target_id,
        "display_name": target.display_name,
        "target_path": str(target_path or target.target_path or ""),
        "matching": {"matches": [dict(match) for match in target.matching.matches]},
    }


def render_full_results_table(
    results: Sequence[ResultItem], *, truncate_messages: bool = False
) -> str:
    """Render the legacy flat results table used in debug and compatibility paths."""
    headers = (
        "Project",
        "Result ID",
        "Category",
        "Severity",
        "Status",
        "Rule",
        "Source",
        "Target",
        "Location",
        "Message",
    )
    rows = []
    for item in results:
        source = entity_to_dict(item.source)
        target_entity = entity_to_dict(item.target)
        message = item.message
        if truncate_messages and len(message) > 160:
            message = message[:157] + "..."
        rows.append(
            (
                item.project_id,
                item.result_id,
                item.category,
                item.severity,
                item.status,
                item.rule_id,
                format_entity(source),
                format_entity(target_entity),
                format_location(source),
                message,
            )
        )
    return render_markdown_table(Table(headers=headers, rows=tuple(rows)))


def sort_rule_groups(groups: Sequence[RuleIssueGroup]) -> tuple[RuleIssueGroup, ...]:
    """Sort groups deterministically for all reader-facing sections."""
    return tuple(
        sorted(
            groups,
            key=lambda group: (
                _GROUP_STATUS_PRIORITY.get(group.display_status, 9),
                _SEVERITY_PRIORITY.get(group.severity.lower(), 9),
                group.rule_id,
            ),
        )
    )


def join_rule_ids(rule_ids: Sequence[str]) -> str:
    """Join rule ids for compact bullet-style summaries."""
    if not rule_ids:
        return "none"
    return ", ".join(escape_markdown(rule_id) for rule_id in rule_ids)


def matching_summary_sentence(presentation: TargetPresentation) -> Optional[str]:
    """Render the compact verdict-level matching note when verbose requires it."""
    summary = presentation.matching_summary
    if summary.visibility != "summary_only":
        return None
    counts: list[str] = []
    if summary.low_confidence:
        counts.append(f"low confidence: {summary.low_confidence}")
    if summary.ambiguous:
        counts.append(f"ambiguous: {summary.ambiguous}")
    if summary.unmatched:
        counts.append(f"unmatched: {summary.unmatched}")
    if not counts:
        return None
    reason = summary.reason or "matching summary explains uncertainty"
    return f"Matching note: {escape_markdown(reason)}" f" ({', '.join(counts)})."


def matching_context_sentence(group: RuleIssueGroup) -> Optional[str]:
    """Render rule-local matching context for warning/skipped diagnostics."""
    if not group.show_matching_context:
        return None

    match_counts = Counter(
        item.match_status
        for item in group.items
        if item.match_status not in {None, "", "matched"}
    )
    parts: list[str] = []
    if group.skipped_count:
        parts.append(f"skipped results: {group.skipped_count}")
    for status, count in sorted(match_counts.items()):
        parts.append(f"{status}: {count}")
    if not parts:
        parts.append("matching anomalies affected this rule")
    return "Matching context: " + ", ".join(parts) + "."


def evidence_summary_sentence(group: RuleIssueGroup) -> Optional[str]:
    """Render the compact evidence summary shown in verbose rule blocks."""
    evidence_count = sum(1 for item in group.items if item.has_evidence)
    if evidence_count == 0:
        return None
    return f"Evidence available for {evidence_count} result(s)."


def render_issue_summary_by_rule(groups: Sequence[RuleIssueGroup]) -> list[str]:
    """Render the issue summary section shared by verbose single/multi target pages."""
    lines = ["## Issue Summary by Rule", ""]
    if not groups:
        lines.append("No failing rules.")
        lines.append("")
        return lines

    rows = tuple(
        (
            group.rule_id,
            group.display_status,
            group.severity,
            str(group.failed_count),
            str(group.warning_count),
            group.summary_message,
        )
        for group in groups
    )
    lines.append(
        render_markdown_table(
            Table(
                headers=("Rule", "Status", "Severity", "Failed", "Warnings", "Summary"),
                rows=rows,
            )
        )
    )
    lines.append("")
    return lines


def render_rule_items_table(group: RuleIssueGroup) -> str:
    """Render the compact item table inside one rule detail block."""
    rows = tuple(
        (
            item.status,
            item.source_display,
            item.target_display,
            item.location_display,
            item.message,
        )
        for item in group.items
    )
    return render_markdown_table(
        Table(
            headers=("Status", "Source", "Target", "Where", "Message"),
            rows=rows,
        )
    )


def render_rule_group_block(group: RuleIssueGroup, *, heading_level: int) -> list[str]:
    """Render one remediation block for a grouped rule."""
    heading = "#" * heading_level
    lines = [f"{heading} {escape_markdown(group.rule_id)}", ""]
    lines.append(f"**Status:** `{escape_markdown(group.display_status)}`")
    lines.append(f"**Severity:** `{escape_markdown(group.severity)}`")
    lines.append(f"**Summary:** {escape_markdown(group.summary_message)}")
    counts = (
        f"failed {group.failed_count}, warnings {group.warning_count}, "
        f"skipped {group.skipped_count}"
    )
    lines.append(f"**Counts:** {counts}")
    lines.append("")
    lines.append(render_rule_items_table(group))
    lines.append("")

    if group.fix_hints:
        lines.append("**Fix hints**")
        for hint in group.fix_hints:
            lines.append(f"- {escape_markdown(hint)}")
        lines.append("")

    matching_note = matching_context_sentence(group)
    if matching_note:
        lines.append(f"**Matching note:** {escape_markdown(matching_note)}")
        lines.append("")

    evidence_note = evidence_summary_sentence(group)
    if evidence_note:
        lines.append(f"**Evidence summary:** {escape_markdown(evidence_note)}")
        lines.append("")

    return lines


def render_compact_passed_summary(presentation: TargetPresentation) -> list[str]:
    """Render the compact passed summary block shared by verbose/debug paths."""
    summary = presentation.compact_passed_summary
    lines = ["## Compact Passed Summary", ""]
    lines.append(f"- Passed checks: {summary.passed_total}")
    if summary.top_passed_rules:
        top_rules = [item.rule_id for item in summary.top_passed_rules]
        lines.append(f"- Top passed rules: {join_rule_ids(top_rules)}")
    else:
        lines.append("- Top passed rules: none")
    lines.append(f"- Hidden passed rows: {summary.hidden_passed_count}")
    lines.append("")
    return lines


def render_rule_hotspots(hotspots: Sequence[RuleHotspot]) -> list[str]:
    """Render ordered hotspot summaries when hotspot data is available."""
    lines = ["## Rule Hotspots", ""]
    if not hotspots:
        lines.append("No recurring rule hotspots.")
        lines.append("")
        return lines
    for hotspot in hotspots:
        severity_mix = ", ".join(
            f"{escape_markdown(severity)}={count}"
            for severity, count in sorted(hotspot.severity_mix.items())
        )
        if not severity_mix:
            severity_mix = "none"
        lines.append(
            f"- {escape_markdown(hotspot.rule_id)}: {hotspot.count} result(s) across "
            f"{hotspot.targets_affected} target(s); severities {severity_mix}"
        )
    lines.append("")
    return lines


def render_standard_target_sections(
    target: TargetReport,
    presentation: TargetPresentation,
    *,
    hotspots: Sequence[RuleHotspot],
) -> list[str]:
    """Render the compact default single-target reader journey."""
    issue_groups = sort_rule_groups(presentation.issue_groups)
    warning_groups = sort_rule_groups(presentation.warning_groups)
    status_counts = escape_markdown(str(target.summary.status_counts))
    severity_counts = escape_markdown(str(target.summary.severity_counts))
    lines: list[str] = [
        "## Verdict",
        "",
        f"- Status: `{escape_markdown(presentation.display_status)}`",
        f"- Exit code: {presentation.exit_code}",
        f"- Target path: {escape_markdown(target.target_path)}",
        "",
        "## Summary",
        "",
        f"- Total results: {target.summary.results_total}",
        f"- Status counts: {status_counts}",
        f"- Severity counts: {severity_counts}",
        "",
    ]
    lines.extend(_render_standard_short_issue_summary(issue_groups))
    if warning_groups:
        lines.extend(_render_standard_warning_summary(warning_groups))
    if presentation.display_status == "OK":
        lines.extend(_render_standard_ok_summary(presentation))
    if hotspots:
        lines.extend(render_rule_hotspots(hotspots))
    return lines


def render_target_detail_sections(
    target: TargetReport, presentation: TargetPresentation
) -> list[str]:
    """Render remediation-first sections for one target."""
    issue_groups = sort_rule_groups(presentation.issue_groups)
    warning_groups = sort_rule_groups(presentation.warning_groups)
    failed_result_count = sum(group.failed_count for group in issue_groups)
    warning_count = sum(group.warning_count for group in issue_groups + warning_groups)

    lines: list[str] = [
        "## Verdict",
        "",
        f"- Status: `{escape_markdown(presentation.display_status)}`",
        f"- Exit code: {presentation.exit_code}",
        f"- Failed rules: {len(issue_groups)}",
        f"- Failed results: {failed_result_count}",
        f"- Warnings: {warning_count}",
        f"- Target path: {escape_markdown(target.target_path)}",
    ]

    matching_sentence = matching_summary_sentence(presentation)
    if matching_sentence:
        lines.append(f"- {matching_sentence}")
    lines.append("")
    lines.extend(render_issue_summary_by_rule(issue_groups))
    lines.append("## Rule Details")
    lines.append("")
    if issue_groups:
        for group in issue_groups:
            lines.extend(render_rule_group_block(group, heading_level=3))
    else:
        lines.append("No failing rule details.")
        lines.append("")

    if warning_groups:
        lines.append("## Warnings")
        lines.append("")
        for group in warning_groups:
            lines.extend(render_rule_group_block(group, heading_level=3))

    lines.extend(render_compact_passed_summary(presentation))
    return lines


def _render_standard_short_issue_summary(groups: Sequence[RuleIssueGroup]) -> list[str]:
    lines = ["## Short Issue Summary", ""]
    if not groups:
        lines.append("No failing rules.")
        lines.append("")
        return lines

    for group in groups:
        lines.append(
            f"- `{escape_markdown(group.rule_id)}`: status "
            f"`{escape_markdown(group.display_status)}`; failed {group.failed_count}; "
            f"{escape_markdown(group.summary_message)}"
        )
    lines.append("")
    return lines


def _render_standard_warning_summary(
    groups: Sequence[RuleIssueGroup],
) -> list[str]:
    lines = ["## Warnings Only", ""]
    for group in groups:
        warning_total = group.warning_count + group.skipped_count
        lines.append(
            f"- `{escape_markdown(group.rule_id)}`: warning-grade results "
            f"{warning_total}; {escape_markdown(group.summary_message)}"
        )
    lines.append("")
    return lines


def _render_standard_ok_summary(presentation: TargetPresentation) -> list[str]:
    lines = ["## OK Summary", ""]
    lines.append("- No actionable issues.")
    lines.append(
        f"- Passed checks: {presentation.compact_passed_summary.passed_total}"
    )
    lines.append("")
    return lines


def render_debug_appendices(
    target: TargetReport,
    presentation: TargetPresentation,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
    target_path: Optional[str] = None,
) -> list[str]:
    """Render all debug-only appendices in the approved fixed order."""
    lines: list[str] = []
    lines.extend(
        _render_matching_debug_appendix(
            target,
            matching_debug_context=matching_debug_context,
            target_path=target_path,
        )
    )
    lines.extend(_render_raw_evidence_appendix(target, presentation))
    lines.extend(_render_full_result_table_appendix(target))
    lines.extend(_render_internal_diagnostics_appendix(target))
    return lines


def _render_matching_debug_appendix(
    target: TargetReport,
    *,
    matching_debug_context: Optional[Dict[str, Any]],
    target_path: Optional[str],
) -> list[str]:
    debug_target = target_debug_report(target, target_path=target_path)
    matching_blocks = build_matching_debug_blocks_for_target(
        debug_target,
        get_target_debug_context(matching_debug_context, debug_target),
        top_k=DEFAULT_MATCHING_DEBUG_TOP_K,
    )
    return [
        "## Matching Debug",
        "",
        render_matching_debug_markdown(
            matching_blocks,
            top_k=DEFAULT_MATCHING_DEBUG_TOP_K,
            heading_level=3,
        ).rstrip(),
        "",
    ]


def _render_raw_evidence_appendix(
    target: TargetReport, presentation: TargetPresentation
) -> list[str]:
    ordered_groups = sort_rule_groups(presentation.issue_groups) + sort_rule_groups(
        presentation.warning_groups
    )
    result_by_id = {item.result_id: item for item in target.results}
    lines = ["## Raw Evidence", ""]
    group_has_evidence = False
    for group in ordered_groups:
        result_items = [
            result_by_id[item.result_id]
            for item in group.items
            if item.result_id in result_by_id and result_by_id[item.result_id].evidence
        ]
        if not result_items:
            continue
        group_has_evidence = True
        lines.append(f"### {escape_markdown(group.rule_id)}")
        lines.append("")
        for result in result_items:
            lines.extend(_render_result_evidence_block(result))
    if not group_has_evidence:
        lines.append("No raw evidence available.")
        lines.append("")
    return lines


def _render_result_evidence_block(result: ResultItem) -> list[str]:
    lines = [f"#### Result {escape_markdown(result.result_id)}", ""]
    lines.append(f"- Status: `{escape_markdown(result.status)}`")
    lines.append(f"- Severity: `{escape_markdown(result.severity)}`")
    lines.append(f"- Message: {escape_markdown(result.message)}")
    lines.append(
        f"- Source: {escape_markdown(_entity_display(result.source, 'unknown source'))}"
    )
    lines.append(
        f"- Target: {escape_markdown(_entity_display(result.target, 'unresolved target'))}"
    )
    lines.append(f"- Location: {escape_markdown(_entity_location_display(result))}")
    lines.append("")

    for index, evidence in enumerate(result.evidence, start=1):
        lines.extend(_render_evidence_item(index, evidence))
    return lines


def _render_evidence_item(index: int, evidence: EvidenceItem) -> list[str]:
    lines = [f"##### Evidence {index}", ""]
    lines.append(f"- Type: `{escape_markdown(evidence.type)}`")
    if evidence.evidence_id:
        lines.append(f"- Evidence ID: `{escape_markdown(evidence.evidence_id)}`")
    if evidence.location_file:
        location = evidence.location_file
        if evidence.location_line is not None:
            location = f"{location}:{evidence.location_line}"
        lines.append(f"- Location: {escape_markdown(location)}")

    payload_text = json.dumps(
        evidence.payload, indent=2, sort_keys=True, ensure_ascii=True
    )
    if payload_text != "{}":
        lines.append("- Payload:")
        lines.append("```json")
        lines.append(payload_text)
        lines.append("```")
    else:
        lines.append("- Payload: {}")
    lines.append("")
    return lines


def _render_full_result_table_appendix(target: TargetReport) -> list[str]:
    lines = ["## Full Result Table", ""]
    if not target.results:
        lines.append("No results.")
        lines.append("")
        return lines
    lines.append(render_full_results_table(target.results))
    lines.append("")
    return lines


def _render_internal_diagnostics_appendix(target: TargetReport) -> list[str]:
    has_top_rules = bool(target.summary.top_rules)
    has_top_source_files = bool(target.summary.top_source_files)
    has_timings = bool(target.summary.timings)
    has_artifacts = bool(target.artifacts)
    has_matching = target.matching.summary.total > 0
    has_matching_config = bool(target.matching.matching_config)
    if not any(
        (
            has_top_rules,
            has_top_source_files,
            has_timings,
            has_artifacts,
            has_matching,
            has_matching_config,
        )
    ):
        return []

    lines = ["## Internal Diagnostics", ""]
    if has_matching:
        summary = target.matching.summary
        lines.append(
            "- Matching summary: "
            f"total {summary.total}, matched {summary.matched}, "
            f"low confidence {summary.low_confidence}, ambiguous {summary.ambiguous}, "
            f"unmatched {summary.unmatched}"
        )
    if has_top_rules:
        lines.append(
            f"- Top rules: {escape_markdown(_json_inline(target.summary.top_rules))}"
        )
    if has_top_source_files:
        lines.append(
            "- Top source files: "
            f"{escape_markdown(_json_inline(target.summary.top_source_files))}"
        )
    if has_artifacts:
        lines.append(f"- Artifacts: {escape_markdown(_json_inline(target.artifacts))}")
    lines.append("")

    if has_timings:
        lines.append("### Timings")
        lines.append("")
        lines.append("```json")
        lines.append(
            json.dumps(
                target.summary.timings, indent=2, sort_keys=True, ensure_ascii=True
            )
        )
        lines.append("```")
        lines.append("")

    if has_matching_config:
        lines.append("### Matching Config")
        lines.append("")
        lines.append("```json")
        lines.append(
            json.dumps(
                target.matching.matching_config,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
            )
        )
        lines.append("```")
        lines.append("")

    return lines


def _entity_display(entity: EntityRef, fallback: str) -> str:
    rendered = format_entity(entity_to_dict(entity))
    return rendered or fallback


def _entity_location_display(result: ResultItem) -> str:
    source = format_location(entity_to_dict(result.source))
    target = format_location(entity_to_dict(result.target))
    if source and target and source != target:
        return f"{source} -> {target}"
    if source:
        return source
    if target:
        return target
    return "unknown location"


def _json_inline(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)
