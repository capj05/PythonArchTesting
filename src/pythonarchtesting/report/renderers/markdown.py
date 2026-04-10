"""Markdown renderer."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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


def _single_target_debug_report(
    target: TargetReport, target_path: Optional[str]
) -> Dict[str, Any]:
    return {
        "display_name": target.display_name,
        "target_id": target.target_id,
        "target_path": str(target_path or ""),
        "matching": {"matches": [dict(match) for match in target.matching.matches]},
    }


def render_markdown(
    document: ReportDocument,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Render typed single-target report document in markdown format."""
    target = document.targets[0]
    results = target.results
    summary = target.summary
    single_target_report = _single_target_debug_report(target, document.run.target_path)
    matching_blocks = build_matching_debug_blocks_for_target(
        single_target_report,
        get_target_debug_context(matching_debug_context, single_target_report),
        top_k=DEFAULT_MATCHING_DEBUG_TOP_K,
    )

    lines: List[str] = [
        "# Validation Report",
        "",
        f"**Generated:** {escape_markdown(str(document.generated_at))}",
        f"**Framework:** {escape_markdown(str(document.framework_version))}",
        f"**Exit Code:** {document.exit_code}",
        "",
        "## Summary",
        "",
        f"- Total Results: {summary.results_total}",
        f"- Status Counts: {escape_markdown(str(summary.status_counts))}",
        f"- Severity Counts: {escape_markdown(str(summary.severity_counts))}",
        f"- Category Counts: {escape_markdown(str(summary.category_counts))}",
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
        target_entity = _entity_to_dict(item.target)
        message = item.message
        if len(message) > 160:
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

    lines.append(render_markdown_table(Table(headers=headers, rows=tuple(rows))))
    lines.append("")
    return "\n".join(lines)
