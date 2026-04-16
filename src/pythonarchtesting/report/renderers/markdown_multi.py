"""Multi-target markdown bundle renderer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Sequence, cast

from pythonarchtesting.report.paths import (
    markdown_bundle_index,
    markdown_target_page,
    resolve_bundle_root,
)

from ..ir.models import ReportDocument, TargetReport
from ..presentation import (
    MarkdownMode,
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
    render_rule_hotspots,
    render_target_detail_sections,
)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_page(path: Path, content: str) -> None:
    _ensure_parent(path)
    path.write_text(content, encoding="utf-8")


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
    label = escape_markdown(card.target_id)
    target_ref = (
        f"[{label}](targets/{card.target_id}.md)"
        if card.has_target_page
        else label
    )
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
    return f"- {target_ref}: {'; '.join(details)}"


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
        "",
        "## Summary",
        "",
        f"- Results total: {document.summary.results.results_total}",
        f"- Result status counts: {escape_markdown(str(document.summary.results.status_counts))}",
        (
            "- Result severity counts: "
            f"{escape_markdown(str(document.summary.results.severity_counts))}"
        ),
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
    if presentation.rule_hotspots:
        lines.extend(render_rule_hotspots(presentation.rule_hotspots))
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
    run_presentation = build_run_presentation(document, mode=mode)

    for target in document.targets:
        target_presentation = build_target_presentation(target, mode=mode)
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
            mode=cast(MarkdownMode, markdown_mode),
            matching_debug_context=matching_debug_context,
        )
    root = resolve_bundle_root(output_root)
    root.mkdir(parents=True, exist_ok=True)
    run_presentation = build_run_presentation(document, mode="standard")
    index_path = markdown_bundle_index(root)
    _write_page(
        index_path,
        _render_run_index_mode(document, run_presentation),
    )
    return str(index_path)
