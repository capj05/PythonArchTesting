"""Multi-target markdown bundle renderer."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pythonarchtesting.report.paths import (
    markdown_bundle_index,
    markdown_target_page,
    resolve_bundle_root,
)

from ..ir.models import EntityRef, ReportDocument, TargetReport
from ..presentation import (
    MarkdownMode,
    RuleHotspot,
    RuleIssueGroup,
    RunPresentation,
    TargetPresentation,
    TargetSummaryCard,
    build_run_presentation,
    build_target_presentation,
)
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


def _entity_to_dict(entity: EntityRef) -> Dict[str, Any]:
    return {
        "module": entity.module,
        "qualname": entity.qualname,
        "file": entity.file,
        "line": entity.line,
    }


def _target_debug_report(target: TargetReport) -> Dict[str, Any]:
    return {
        "target_id": target.target_id,
        "display_name": target.display_name,
        "target_path": target.target_path,
        "matching": {"matches": [dict(match) for match in target.matching.matches]},
    }


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_page(path: Path, content: str) -> None:
    _ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def _target_summary_rows(targets: List[TargetReport]) -> tuple[tuple[str, ...], ...]:
    rows: List[tuple[str, ...]] = []
    for target in targets:
        rows.append(
            (
                target.target_id,
                target.target_path,
                str(target.exit_code),
                str(target.summary.results_total),
                str(target.summary.status_counts.get("FAILED", 0)),
            )
        )
    return tuple(rows)


def _render_target_page_legacy(
    document: ReportDocument,
    target: TargetReport,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
) -> str:
    results = target.results
    debug_target = _target_debug_report(target)
    matching_blocks = build_matching_debug_blocks_for_target(
        debug_target,
        get_target_debug_context(matching_debug_context, debug_target),
        top_k=DEFAULT_MATCHING_DEBUG_TOP_K,
    )
    lines: List[str] = [
        f"# Target Report: {escape_markdown(target.target_id)}",
        "",
        "[Back to run index](../report.md)",
        "",
        "## Metadata",
        "",
        f"- Target ID: {escape_markdown(target.target_id)}",
        f"- Path: {escape_markdown(target.target_path)}",
        f"- Exit Code: {target.exit_code}",
        "",
        "## Summary",
        "",
        f"- Total Results: {target.summary.results_total}",
        f"- Status Counts: {escape_markdown(str(target.summary.status_counts))}",
        f"- Severity Counts: {escape_markdown(str(target.summary.severity_counts))}",
        f"- Category Counts: {escape_markdown(str(target.summary.category_counts))}",
        "",
        "## Matching",
        "",
        f"- Total: {target.matching.summary.total}",
        f"- Matched: {target.matching.summary.matched}",
        f"- Low confidence: {target.matching.summary.low_confidence}",
        f"- Ambiguous: {target.matching.summary.ambiguous}",
        f"- Unmatched: {target.matching.summary.unmatched}",
        "",
        render_matching_debug_markdown(
            matching_blocks,
            top_k=DEFAULT_MATCHING_DEBUG_TOP_K,
            heading_level=2,
        ).rstrip(),
        "",
        "## Results",
        "",
    ]

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
        source = _entity_to_dict(item.source)
        target_ref = _entity_to_dict(item.target)
        rows.append(
            (
                item.project_id,
                item.result_id,
                item.category,
                item.severity,
                item.status,
                item.rule_id,
                format_entity(source),
                format_entity(target_ref),
                format_location(source),
                item.message,
            )
        )
    lines.append(render_markdown_table(Table(headers=headers, rows=tuple(rows))))
    lines.append("")
    return "\n".join(lines)


def _render_markdown_bundle_legacy(
    document: ReportDocument,
    output_root: Path,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Write a deterministic multi-target markdown bundle and return index path."""
    root = resolve_bundle_root(output_root)
    root.mkdir(parents=True, exist_ok=True)

    targets = list(document.targets)

    for target in targets:
        page_path = markdown_target_page(root, target.target_id or "target")
        _write_page(
            page_path,
            _render_target_page_legacy(
                document,
                target,
                matching_debug_context=matching_debug_context,
            ),
        )

    index_lines: List[str] = [
        "# Validation Run Report",
        "",
        f"**Generated:** {escape_markdown(str(document.generated_at))}",
        f"**Framework:** {escape_markdown(str(document.framework_version))}",
        f"**Source:** {escape_markdown(str(document.run.source_path or ''))}",
        f"**Exit Code:** {document.exit_code}",
        "",
        "## Run Summary",
        "",
        f"- Targets total: {document.summary.targets_total or len(targets)}",
        f"- Targets passed: {document.summary.targets_passed or 0}",
        f"- Targets failed: {document.summary.targets_failed or 0}",
        "",
        "## Targets",
        "",
    ]
    index_lines.append(
        render_markdown_table(
            Table(
                headers=("Target", "Path", "Exit", "Results", "Failed"),
                rows=_target_summary_rows(targets),
            )
        )
    )
    index_lines.append("")
    for target in targets:
        tid = target.target_id or "target"
        index_lines.append(f"- [{escape_markdown(tid)}](targets/{tid}.md)")
    index_lines.append("")

    index_path = markdown_bundle_index(root)
    _write_page(index_path, "\n".join(index_lines))
    return str(index_path)


def _sort_rule_groups(groups: Sequence[RuleIssueGroup]) -> tuple[RuleIssueGroup, ...]:
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


def _join_rule_ids(rule_ids: Sequence[str]) -> str:
    if not rule_ids:
        return "none"
    return ", ".join(escape_markdown(rule_id) for rule_id in rule_ids)


def _matching_summary_sentence(presentation: TargetPresentation) -> Optional[str]:
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


def _matching_context_sentence(group: RuleIssueGroup) -> Optional[str]:
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


def _evidence_summary_sentence(group: RuleIssueGroup) -> Optional[str]:
    evidence_count = sum(1 for item in group.items if item.has_evidence)
    if evidence_count == 0:
        return None
    return f"Evidence available for {evidence_count} result(s)."


def _render_issue_summary_by_rule(groups: Sequence[RuleIssueGroup]) -> list[str]:
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


def _render_rule_items_table(group: RuleIssueGroup) -> str:
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


def _render_rule_group_block(group: RuleIssueGroup, *, heading_level: int) -> list[str]:
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
    lines.append(_render_rule_items_table(group))
    lines.append("")

    if group.fix_hints:
        lines.append("**Fix hints**")
        for hint in group.fix_hints:
            lines.append(f"- {escape_markdown(hint)}")
        lines.append("")

    matching_note = _matching_context_sentence(group)
    if matching_note:
        lines.append(f"**Matching note:** {escape_markdown(matching_note)}")
        lines.append("")

    evidence_note = _evidence_summary_sentence(group)
    if evidence_note:
        lines.append(f"**Evidence summary:** {escape_markdown(evidence_note)}")
        lines.append("")

    return lines


def _render_compact_passed_summary(presentation: TargetPresentation) -> list[str]:
    summary = presentation.compact_passed_summary
    lines = ["## Compact Passed Summary", ""]
    lines.append(f"- Passed checks: {summary.passed_total}")
    if summary.top_passed_rules:
        top_rules = [item.rule_id for item in summary.top_passed_rules]
        lines.append(f"- Top passed rules: {_join_rule_ids(top_rules)}")
    else:
        lines.append("- Top passed rules: none")
    lines.append(f"- Hidden passed rows: {summary.hidden_passed_count}")
    lines.append("")
    return lines


def _render_target_page_verbose(
    target: TargetReport, presentation: TargetPresentation
) -> str:
    issue_groups = _sort_rule_groups(presentation.issue_groups)
    warning_groups = _sort_rule_groups(presentation.warning_groups)
    failed_result_count = sum(group.failed_count for group in issue_groups)
    warning_count = sum(group.warning_count for group in issue_groups + warning_groups)
    lines: list[str] = [
        f"# Target Report: {escape_markdown(presentation.display_name)}",
        "",
        "[Back to run index](../report.md)",
        "",
        "## Verdict",
        "",
        f"- Status: `{escape_markdown(presentation.display_status)}`",
        f"- Exit code: {presentation.exit_code}",
        f"- Failed rules: {len(issue_groups)}",
        f"- Failed results: {failed_result_count}",
        f"- Warnings: {warning_count}",
        f"- Target path: {escape_markdown(target.target_path)}",
    ]

    matching_sentence = _matching_summary_sentence(presentation)
    if matching_sentence:
        lines.append(f"- {matching_sentence}")
    lines.append("")
    lines.extend(_render_issue_summary_by_rule(issue_groups))
    lines.append("## Rule Details")
    lines.append("")
    if issue_groups:
        for group in issue_groups:
            lines.extend(_render_rule_group_block(group, heading_level=3))
    else:
        lines.append("No failing rule details.")
        lines.append("")

    if warning_groups:
        lines.append("## Warnings")
        lines.append("")
        for group in warning_groups:
            lines.extend(_render_rule_group_block(group, heading_level=3))

    lines.extend(_render_compact_passed_summary(presentation))
    return "\n".join(lines)


def _render_target_card(card: TargetSummaryCard) -> str:
    link = f"[{escape_markdown(card.target_id)}](targets/{card.target_id}.md)"
    details = [
        f"status `{escape_markdown(card.display_status)}`",
        f"exit {card.exit_code}",
        f"issues {card.issue_count}",
        f"warnings {card.warning_count}",
    ]
    if card.top_rule_ids:
        details.append(f"top rules: {_join_rule_ids(card.top_rule_ids)}")
    if card.has_matching_anomalies:
        details.append("matching anomalies present")
    return f"- {link}: {'; '.join(details)}"


def _render_target_section(
    heading: str, cards: Sequence[TargetSummaryCard], empty_message: str
) -> list[str]:
    lines = [f"## {heading}", ""]
    if not cards:
        lines.append(empty_message)
        lines.append("")
        return lines
    for card in cards:
        lines.append(_render_target_card(card))
    lines.append("")
    return lines


def _render_rule_hotspots(hotspots: Sequence[RuleHotspot]) -> list[str]:
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


def _render_run_index_verbose(
    document: ReportDocument, presentation: RunPresentation
) -> str:
    issue_cards = tuple(presentation.error_targets) + tuple(
        presentation.targets_with_issues
    )
    lines: list[str] = [
        f"# {escape_markdown(presentation.title)}",
        "",
        f"**Generated:** {escape_markdown(str(document.generated_at))}",
        f"**Framework:** {escape_markdown(str(document.framework_version))}",
        f"**Source:** {escape_markdown(str(document.run.source_path or ''))}",
        f"**Exit Code:** {document.exit_code}",
        "",
        "## Verdict",
        "",
        f"- Status: `{escape_markdown(presentation.display_status)}`",
        f"- Exit code: {presentation.exit_code}",
        f"- Targets total: {presentation.targets_total}",
        f"- Targets with issues: {presentation.targets_issues + presentation.targets_error}",
        f"- Warnings only: {presentation.targets_warnings_only}",
        f"- OK targets: {presentation.targets_ok}",
        "",
    ]
    lines.extend(
        _render_target_section(
            "Targets With Issues",
            issue_cards,
            "No failing targets.",
        )
    )
    if presentation.warnings_only_targets:
        lines.extend(
            _render_target_section(
                "Warnings Only",
                presentation.warnings_only_targets,
                "No warnings-only targets.",
            )
        )
    lines.extend(
        _render_target_section(
            "OK Targets",
            presentation.ok_targets,
            "No OK targets.",
        )
    )
    lines.extend(_render_rule_hotspots(presentation.rule_hotspots))
    return "\n".join(lines)


def render_markdown_bundle_mode(
    document: ReportDocument,
    output_root: Path,
    *,
    mode: MarkdownMode,
    matching_debug_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Write a multi-target markdown bundle for an internal mode-specific path."""
    del matching_debug_context
    if mode != "verbose":
        raise ValueError(
            f"Unsupported internal multi-target markdown mode '{mode}'. "
            "Only 'verbose' is implemented."
        )

    root = resolve_bundle_root(output_root)
    root.mkdir(parents=True, exist_ok=True)
    run_presentation = build_run_presentation(document, mode="verbose")

    for target in document.targets:
        target_presentation = build_target_presentation(target, mode="verbose")
        page_path = markdown_target_page(root, target.target_id or "target")
        _write_page(page_path, _render_target_page_verbose(target, target_presentation))

    index_path = markdown_bundle_index(root)
    _write_page(index_path, _render_run_index_verbose(document, run_presentation))
    return str(index_path)


def render_markdown_bundle(
    document: ReportDocument,
    output_root: Path,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Write a deterministic multi-target markdown bundle and return index path."""
    return _render_markdown_bundle_legacy(
        document,
        output_root,
        matching_debug_context=matching_debug_context,
    )
