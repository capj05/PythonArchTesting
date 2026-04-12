"""Multi-target markdown bundle renderer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pythonarchtesting.report.paths import (
    markdown_bundle_index,
    markdown_target_page,
    resolve_bundle_root,
)

from ..ir.models import ReportDocument, TargetReport
from ..presentation import (
    MarkdownMode,
    RuleHotspot,
    RunPresentation,
    TargetPresentation,
    TargetSummaryCard,
    build_run_presentation,
    build_target_presentation,
)
from .escape import escape_markdown
from .markdown_sections import (
    join_rule_ids,
    render_debug_appendices,
    render_full_results_table,
    render_target_detail_sections,
    target_debug_report,
)
from .matching_debug import (
    DEFAULT_MATCHING_DEBUG_TOP_K,
    build_matching_debug_blocks_for_target,
    get_target_debug_context,
    render_matching_debug_markdown,
)
from .table import Table, render_markdown_table


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
    debug_target = target_debug_report(target)
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
    lines.append(render_full_results_table(target.results))
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


def _render_target_page_verbose(
    target: TargetReport, presentation: TargetPresentation
) -> str:
    lines: list[str] = [
        f"# Target Report: {escape_markdown(presentation.display_name)}",
        "",
        "[Back to run index](../report.md)",
        "",
    ]
    lines.extend(render_target_detail_sections(target, presentation))
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
        details.append(f"top rules: {join_rule_ids(card.top_rule_ids)}")
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


def _render_target_page_debug(
    target: TargetReport,
    presentation: TargetPresentation,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
) -> str:
    lines = [
        _render_target_page_verbose(target, presentation),
        "",
    ]
    lines.extend(
        render_debug_appendices(
            target,
            presentation,
            matching_debug_context=matching_debug_context,
        )
    )
    return "\n".join(lines)


def _render_run_index_mode(
    document: ReportDocument,
    presentation: RunPresentation,
    *,
    debug: bool = False,
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
    ]
    if debug:
        lines.append("- Debug appendices: available on target pages.")
    lines.append("")
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
    if mode not in {"verbose", "debug"}:
        raise ValueError(
            f"Unsupported internal multi-target markdown mode '{mode}'. "
            "Only 'verbose' and 'debug' are implemented."
        )

    root = resolve_bundle_root(output_root)
    root.mkdir(parents=True, exist_ok=True)
    run_presentation = build_run_presentation(document, mode="verbose")

    for target in document.targets:
        target_presentation = build_target_presentation(target, mode="verbose")
        page_path = markdown_target_page(root, target.target_id or "target")
        if mode == "debug":
            content = _render_target_page_debug(
                target,
                target_presentation,
                matching_debug_context=matching_debug_context,
            )
        else:
            content = _render_target_page_verbose(target, target_presentation)
        _write_page(page_path, content)

    index_path = markdown_bundle_index(root)
    _write_page(
        index_path,
        _render_run_index_mode(document, run_presentation, debug=(mode == "debug")),
    )
    return str(index_path)


def render_markdown_bundle(
    document: ReportDocument,
    output_root: Path,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
    markdown_mode: str = "standard",
) -> str:
    """Write a deterministic multi-target markdown bundle and return index path."""
    if markdown_mode != "standard":
        return render_markdown_bundle_mode(
            document,
            output_root,
            mode=markdown_mode,
            matching_debug_context=matching_debug_context,
        )
    return _render_markdown_bundle_legacy(
        document,
        output_root,
        matching_debug_context=matching_debug_context,
    )
