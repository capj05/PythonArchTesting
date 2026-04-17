"""Multi-target markdown bundle renderer."""

from __future__ import annotations

import shutil
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
    render_target_detail_sections,
)
from .table import Table, render_markdown_table


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_page(path: Path, content: str) -> None:
    _ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def _cleanup_standard_bundle(root: Path) -> None:
    targets_dir = root / "targets"
    if targets_dir.is_dir():
        shutil.rmtree(targets_dir)


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


def _render_verbose_run_index(
    document: ReportDocument,
    presentation: RunPresentation,
) -> str:
    return _render_triage_run_index(
        document,
        presentation,
        link_targets=True,
    )


def _render_debug_run_index(
    document: ReportDocument,
    presentation: RunPresentation,
) -> str:
    return _render_triage_run_index(
        document,
        presentation,
        link_targets=True,
    )


def _render_standard_run_index(
    document: ReportDocument,
    presentation: RunPresentation,
) -> str:
    return _render_triage_run_index(
        document,
        presentation,
        link_targets=False,
    )


def _render_triage_run_index(
    document: ReportDocument,
    presentation: RunPresentation,
    *,
    link_targets: bool,
) -> str:
    issue_cards = _sort_issue_cards(
        tuple(presentation.error_targets) + tuple(presentation.targets_with_issues)
    )
    warning_cards = _sort_warning_cards(presentation.warnings_only_targets)
    passed_cards = _sort_passed_cards(presentation.ok_targets)
    lines: list[str] = [
        f"# {escape_markdown(presentation.title)}",
        "",
        f"> **Verdict:** {escape_markdown(presentation.display_status)}",
        (
            "> **Projects:** "
            f"{presentation.targets_total} total | "
            f"**Passed:** {presentation.targets_ok} | "
            f"**Issues:** {presentation.targets_error + presentation.targets_issues} | "
            f"**Warnings only:** {presentation.targets_warnings_only}"
        ),
        f"> **Exit code:** {presentation.exit_code}",
        "",
    ]
    lines.extend(_render_standard_at_a_glance(presentation))
    lines.extend(_render_standard_issue_table(issue_cards, link_targets=link_targets))
    if issue_cards and presentation.failing_rule_hotspots:
        lines.extend(_render_standard_common_failure_causes(presentation))
    if warning_cards:
        lines.extend(
            _render_standard_warning_table(warning_cards, link_targets=link_targets)
        )
    if passed_cards:
        lines.extend(
            _render_standard_passed_projects(passed_cards, link_targets=link_targets)
        )
    lines.extend(_render_standard_run_metadata(document))
    return "\n".join(lines)


def _sort_issue_cards(
    cards: Sequence[TargetSummaryCard],
) -> tuple[TargetSummaryCard, ...]:
    status_priority = {"ERROR": 0, "ISSUES": 1}
    return tuple(
        sorted(
            cards,
            key=lambda card: (
                status_priority.get(card.display_status, 9),
                -card.failed_check_count,
                card.target_id,
            ),
        )
    )


def _sort_warning_cards(
    cards: Sequence[TargetSummaryCard],
) -> tuple[TargetSummaryCard, ...]:
    return tuple(
        sorted(cards, key=lambda card: (-card.warning_only_count, card.target_id))
    )


def _sort_passed_cards(
    cards: Sequence[TargetSummaryCard],
) -> tuple[TargetSummaryCard, ...]:
    return tuple(
        sorted(cards, key=lambda card: (-card.passed_check_count, card.target_id))
    )


def _render_standard_at_a_glance(presentation: RunPresentation) -> list[str]:
    rows = (
        ("Total projects", str(presentation.targets_total)),
        ("Passed", str(presentation.targets_ok)),
        ("With issues", str(presentation.targets_error + presentation.targets_issues)),
        ("Warnings only", str(presentation.targets_warnings_only)),
        ("Distinct failing rules", str(presentation.distinct_failing_rules)),
    )
    return [
        "## At a glance",
        "",
        render_markdown_table(Table(headers=("Metric", "Count"), rows=rows)),
        "",
    ]


def _render_standard_issue_table(
    cards: Sequence[TargetSummaryCard],
    *,
    link_targets: bool = False,
) -> list[str]:
    lines = ["## Projects with issues", ""]
    if not cards:
        lines.append("No projects with issues.")
        lines.append("")
        return lines
    rows = tuple(
        (
            _render_project_name_cell(card, link_targets=link_targets),
            card.display_status,
            str(card.failed_rule_count),
            str(card.failed_check_count),
            card.main_problems or join_rule_ids(card.top_rule_ids),
        )
        for card in cards
    )
    lines.append(
        render_markdown_table(
            Table(
                headers=(
                    "Project",
                    "Status",
                    "Failed rules",
                    "Failed checks",
                    "Main problems",
                ),
                rows=rows,
            )
        )
    )
    lines.append("")
    return lines


def _render_standard_common_failure_causes(presentation: RunPresentation) -> list[str]:
    rows = tuple(
        (
            f"`{hotspot.rule_id}`",
            str(hotspot.targets_affected),
            str(hotspot.count),
        )
        for hotspot in presentation.failing_rule_hotspots
    )
    return [
        "## Common failure causes",
        "",
        render_markdown_table(
            Table(
                headers=("Rule", "Projects affected", "Failed checks"),
                rows=rows,
            )
        ),
        "",
    ]


def _render_standard_warning_table(
    cards: Sequence[TargetSummaryCard],
    *,
    link_targets: bool = False,
) -> list[str]:
    rows = tuple(
        (
            _render_project_name_cell(card, link_targets=link_targets),
            str(card.warning_only_count),
            card.main_reason or join_rule_ids(card.top_rule_ids),
        )
        for card in cards
    )
    return [
        "## Projects with warnings only",
        "",
        render_markdown_table(
            Table(headers=("Project", "Warning count", "Main reason"), rows=rows)
        ),
        "",
    ]


def _render_standard_passed_projects(
    cards: Sequence[TargetSummaryCard],
    *,
    link_targets: bool = False,
) -> list[str]:
    rows = tuple(
        (
            _render_project_name_cell(card, link_targets=link_targets),
            str(card.passed_check_count),
        )
        for card in cards
    )
    return [
        "<details>",
        f"<summary><strong>Passed projects ({len(cards)})</strong></summary>",
        "",
        render_markdown_table(Table(headers=("Project", "Checks"), rows=rows)),
        "",
        "</details>",
        "",
    ]


def _render_standard_run_metadata(document: ReportDocument) -> list[str]:
    lines = [
        "---",
        "",
        "## Run metadata",
        "",
        f"- Generated: {escape_markdown(str(document.generated_at))}",
        f"- Framework: {escape_markdown(str(document.framework_version))}",
        f"- Source: {escape_markdown(str(document.run.source_path or ''))}",
    ]
    exit_policy = _resolve_exit_policy(document)
    if exit_policy:
        lines.append(f"- Exit policy: {escape_markdown(exit_policy)}")
    lines.append("")
    return lines


def _resolve_exit_policy(document: ReportDocument) -> str | None:
    snapshot = document.run.config_snapshot or {}
    report_section = snapshot.get("report", {})
    value = report_section.get("multi_target_exit_policy")
    if value:
        return str(value)
    return None


def _render_project_name_cell(
    card: TargetSummaryCard,
    *,
    link_targets: bool,
) -> str:
    label = escape_markdown(card.display_name)
    if link_targets and card.has_target_page:
        return f"[{label}](targets/{card.target_id}.md)"
    return label


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
        (
            _render_debug_run_index(document, run_presentation)
            if mode == "debug"
            else _render_verbose_run_index(document, run_presentation)
        ),
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
    _cleanup_standard_bundle(root)
    run_presentation = build_run_presentation(document, mode="standard")
    index_path = markdown_bundle_index(root)
    _write_page(
        index_path,
        _render_standard_run_index(document, run_presentation),
    )
    return str(index_path)
