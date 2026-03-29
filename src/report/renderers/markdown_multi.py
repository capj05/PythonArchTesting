"""Multi-target markdown bundle renderer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from src.report.paths import (
    markdown_bundle_index,
    markdown_target_page,
    resolve_bundle_root,
)

from .common import format_entity, format_location, summarize_matching
from .escape import escape_markdown
from .matching_debug import (
    DEFAULT_MATCHING_DEBUG_TOP_K,
    build_matching_debug_blocks_for_target,
    get_target_debug_context,
    render_matching_debug_markdown,
)
from .table import Table, render_markdown_table


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _target_summary_rows(targets: List[Dict[str, Any]]) -> tuple[tuple[str, ...], ...]:
    rows: List[tuple[str, ...]] = []
    for target in targets:
        summary = target.get("summary") or {}
        rows.append(
            (
                str(target.get("target_id") or ""),
                str(target.get("target_path") or ""),
                str(target.get("exit_code", 0)),
                str(summary.get("results_total", 0)),
                str((summary.get("status_counts") or {}).get("FAILED", 0)),
            )
        )
    return tuple(rows)


def _render_target_page(
    report: Dict[str, Any],
    target: Dict[str, Any],
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
) -> str:
    summary = target.get("summary") or {}
    results = target.get("results") or []
    matching_summary = summarize_matching(target.get("matching") or {})
    matching_blocks = build_matching_debug_blocks_for_target(
        target,
        get_target_debug_context(matching_debug_context, target),
        top_k=DEFAULT_MATCHING_DEBUG_TOP_K,
    )
    lines: List[str] = [
        f"# Target Report: {escape_markdown(str(target.get('target_id') or ''))}",
        "",
        "[Back to run index](../report.md)",
        "",
        "## Metadata",
        "",
        f"- Target ID: {escape_markdown(str(target.get('target_id') or ''))}",
        f"- Path: {escape_markdown(str(target.get('target_path') or ''))}",
        f"- Exit Code: {target.get('exit_code', 0)}",
        "",
        "## Summary",
        "",
        f"- Total Results: {summary.get('results_total', len(results))}",
        f"- Status Counts: {escape_markdown(str(summary.get('status_counts', {})))}",
        f"- Severity Counts: {escape_markdown(str(summary.get('severity_counts', {})))}",
        f"- Category Counts: {escape_markdown(str(summary.get('category_counts', {})))}",
        "",
        "## Matching",
        "",
        f"- Total: {matching_summary.get('total', 0)}",
        f"- Matched: {matching_summary.get('matched', 0)}",
        f"- Low confidence: {matching_summary.get('low_confidence', 0)}",
        f"- Ambiguous: {matching_summary.get('ambiguous', 0)}",
        f"- Unmatched: {matching_summary.get('unmatched', 0)}",
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
        target_ref = item.get("target") or {}
        rows.append(
            (
                str(item.get("project_id") or ""),
                str(item.get("result_id") or ""),
                str(item.get("category") or ""),
                str(item.get("severity") or ""),
                str(item.get("status") or ""),
                str(item.get("rule_id") or ""),
                format_entity(source),
                format_entity(target_ref),
                format_location(source),
                str(item.get("message") or ""),
            )
        )
    lines.append(render_markdown_table(Table(headers=headers, rows=tuple(rows))))
    lines.append("")
    return "\n".join(lines)


def render_markdown_bundle(
    report: Dict[str, Any],
    output_root: Path,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Write a deterministic multi-target markdown bundle and return index path."""
    root = resolve_bundle_root(output_root)
    root.mkdir(parents=True, exist_ok=True)

    targets = list(report.get("targets") or [])
    summary = report.get("summary") or {}
    run = report.get("run") or {}

    for target in targets:
        page_path = markdown_target_page(root, str(target.get("target_id") or "target"))
        _ensure_parent(page_path)
        page_path.write_text(
            _render_target_page(
                report,
                target,
                matching_debug_context=matching_debug_context,
            ),
            encoding="utf-8",
        )

    index_lines: List[str] = [
        "# Validation Run Report",
        "",
        f"**Generated:** {escape_markdown(str(report.get('generated_at', '')))}",
        f"**Framework:** {escape_markdown(str(report.get('framework_version', '')))}",
        f"**Source:** {escape_markdown(str(run.get('source_path', '')))}",
        f"**Exit Code:** {report.get('exit_code', 0)}",
        "",
        "## Run Summary",
        "",
        f"- Targets total: {summary.get('targets_total', len(targets))}",
        f"- Targets passed: {summary.get('targets_passed', 0)}",
        f"- Targets failed: {summary.get('targets_failed', 0)}",
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
        tid = str(target.get("target_id") or "target")
        index_lines.append(f"- [{escape_markdown(tid)}](targets/{tid}.md)")
    index_lines.append("")

    index_path = markdown_bundle_index(root)
    index_path.write_text("\n".join(index_lines), encoding="utf-8")
    return str(index_path)
