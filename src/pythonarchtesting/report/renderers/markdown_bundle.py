"""Markdown bundle renderer for run reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pythonarchtesting.report.paths import (
    markdown_bundle_index,
    markdown_target_page,
    resolve_bundle_root,
)

from ..ir.models import EntityRef, ReportDocument, TargetReport
from .common import format_entity, format_location
from .escape import escape_markdown
from .matching_debug import (
    DEFAULT_MATCHING_DEBUG_TOP_K,
    build_matching_debug_blocks_for_target,
    get_target_debug_context,
    render_matching_debug_markdown,
)
from .table import Table, render_markdown_table


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


def _render_target_page(
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


def render_markdown_bundle(
    document: ReportDocument,
    output_root: Path,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Write a deterministic Markdown bundle for a run report and return the index path."""
    root = resolve_bundle_root(output_root)
    root.mkdir(parents=True, exist_ok=True)

    targets = list(document.targets)

    for target in targets:
        page_path = markdown_target_page(root, target.target_id or "target")
        _ensure_parent(page_path)
        page_path.write_text(
            _render_target_page(
                document,
                target,
                matching_debug_context=matching_debug_context,
            ),
            encoding="utf-8",
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
    index_path.write_text("\n".join(index_lines), encoding="utf-8")
    return str(index_path)
