"""Markdown renderer."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .common import format_entity, format_location
from .escape import escape_markdown
from .matching_debug import (
    DEFAULT_MATCHING_DEBUG_TOP_K,
    build_matching_debug_blocks_for_target,
    get_target_debug_context,
    render_matching_debug_markdown,
)
from .table import Table, render_markdown_table


def render_markdown(
    report: Dict[str, Any],
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Render canonical schema-v2 report in markdown format."""
    results = report.get("results", []) or []
    summary = report.get("summary", {}) or {}
    single_target_report = {
        "display_name": "__single__",
        "target_id": "__single__",
        "target_path": str((report.get("run") or {}).get("target_path") or ""),
        "matching": report.get("matching") or {},
    }
    matching_blocks = build_matching_debug_blocks_for_target(
        single_target_report,
        get_target_debug_context(matching_debug_context, single_target_report),
        top_k=DEFAULT_MATCHING_DEBUG_TOP_K,
    )

    lines: List[str] = [
        "# Validation Report",
        "",
        f"**Generated:** {escape_markdown(str(report.get('generated_at', '')))}",
        f"**Framework:** {escape_markdown(str(report.get('framework_version', '')))}",
        f"**Exit Code:** {report.get('exit_code', 0)}",
        "",
        "## Summary",
        "",
        f"- Total Results: {summary.get('results_total', len(results))}",
        f"- Status Counts: {escape_markdown(str(summary.get('status_counts', {})))}",
        f"- Severity Counts: {escape_markdown(str(summary.get('severity_counts', {})))}",
        f"- Category Counts: {escape_markdown(str(summary.get('category_counts', {})))}",
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
        source = item.get("source") or {}
        target = item.get("target") or {}
        message = str(item.get("message") or "")
        if len(message) > 160:
            message = message[:157] + "..."
        rows.append(
            (
                str(item.get("project_id") or ""),
                str(item.get("result_id") or ""),
                str(item.get("category") or ""),
                str(item.get("severity") or ""),
                str(item.get("status") or ""),
                str(item.get("rule_id") or ""),
                format_entity(source),
                format_entity(target),
                format_location(source),
                message,
            )
        )

    lines.append(render_markdown_table(Table(headers=headers, rows=tuple(rows))))
    lines.append("")
    return "\n".join(lines)
