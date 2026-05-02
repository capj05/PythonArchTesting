"""Markdown bundle renderer for run reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

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


def _format_count_dict(counts: Mapping[str, int]) -> str:
    return " · ".join(f"{escape_markdown(str(k))}: {v}" for k, v in counts.items())


def _target_summary_rows(targets: List[TargetReport]) -> tuple[tuple[str, ...], ...]:
    rows: List[tuple[str, ...]] = []
    for target in targets:
        tid = target.target_id or "target"
        rows.append(
            (
                f"[{escape_markdown(tid)}](targets/{tid}.md)",
                target.target_path,
                str(target.exit_code),
                str(target.summary.results_total),
                str(target.summary.status_counts.get("FAILED", 0)),
            )
        )
    return tuple(rows)


_VALID_DETAIL_LEVELS = ("summary", "verbose", "debug")


def _normalize_detail(level: Optional[str]) -> str:
    if level is None:
        return "verbose"
    normalized = str(level).strip().lower()
    if normalized not in _VALID_DETAIL_LEVELS:
        return "verbose"
    return normalized


def _render_target_page(
    document: ReportDocument,
    target: TargetReport,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
    include_back_link: bool = True,
    detail: str = "verbose",
) -> str:
    results = target.results
    detail = _normalize_detail(detail)
    lines: List[str] = [
        f"# Target Report: {escape_markdown(target.target_id)}",
        "",
    ]
    if include_back_link:
        lines.extend(["[Back to run index](../report.md)", ""])
    lines.extend([
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
    ])
    if detail in ("verbose", "debug"):
        lines.extend([
            "## Matching",
            "",
            f"- Total: {target.matching.summary.total}",
            f"- Matched: {target.matching.summary.matched}",
            f"- Low confidence: {target.matching.summary.low_confidence}",
            f"- Ambiguous: {target.matching.summary.ambiguous}",
            f"- Unmatched: {target.matching.summary.unmatched}",
            "",
        ])
    if detail == "debug":
        debug_target = _target_debug_report(target)
        matching_blocks = build_matching_debug_blocks_for_target(
            debug_target,
            get_target_debug_context(matching_debug_context, debug_target),
            top_k=DEFAULT_MATCHING_DEBUG_TOP_K,
        )
        lines.extend([
            render_matching_debug_markdown(
                matching_blocks,
                top_k=DEFAULT_MATCHING_DEBUG_TOP_K,
                heading_level=2,
            ).rstrip(),
            "",
        ])
    lines.extend([
        "## Results",
        "",
    ])

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


def render_markdown_single_target(
    document: ReportDocument,
    output_path: Path,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
    detail: str = "verbose",
) -> str:
    """Render a single-target Markdown report to one file. Returns the path."""
    targets = list(document.targets)
    if len(targets) != 1:
        raise ValueError(
            "render_markdown_single_target requires exactly one target."
        )
    target = targets[0]
    rendered = _render_target_page(
        document,
        target,
        matching_debug_context=matching_debug_context,
        include_back_link=False,
        detail=detail,
    )
    _ensure_parent(output_path)
    output_path.write_text(rendered, encoding="utf-8")
    return str(output_path)


def render_markdown_bundle(
    document: ReportDocument,
    output_root: Path,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
    detail: str = "verbose",
) -> str:
    """Write a deterministic Markdown bundle for a run report and return the index path."""
    root = resolve_bundle_root(output_root)
    root.mkdir(parents=True, exist_ok=True)

    targets = list(document.targets)
    detail = _normalize_detail(detail)

    for target in targets:
        page_path = markdown_target_page(root, target.target_id or "target")
        _ensure_parent(page_path)
        page_path.write_text(
            _render_target_page(
                document,
                target,
                matching_debug_context=matching_debug_context,
                detail=detail,
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
    ]

    if detail in ("verbose", "debug"):
        results_summary = document.summary.results
        if results_summary.results_total > 0:
            index_lines.extend([
                "## Result Totals",
                "",
                f"- Total Results: {results_summary.results_total}",
            ])
            if results_summary.status_counts:
                index_lines.append(
                    f"- Status Counts: {_format_count_dict(results_summary.status_counts)}"
                )
            if results_summary.severity_counts:
                index_lines.append(
                    f"- Severity Counts: {_format_count_dict(results_summary.severity_counts)}"
                )
            if results_summary.category_counts:
                index_lines.append(
                    f"- Category Counts: {_format_count_dict(results_summary.category_counts)}"
                )
            index_lines.append("")
        if results_summary.top_rules:
            index_lines.extend([
                "## Top Rules by Violation Count",
                "",
                render_markdown_table(
                    Table(
                        headers=("Rule", "Violations"),
                        rows=tuple(
                            (
                                escape_markdown(str(entry.get("name") or "")),
                                str(entry.get("count") or 0),
                            )
                            for entry in results_summary.top_rules
                        ),
                    )
                ),
                "",
            ])
        if results_summary.top_source_files:
            index_lines.extend([
                "## Top Source Files",
                "",
                render_markdown_table(
                    Table(
                        headers=("File", "Results"),
                        rows=tuple(
                            (
                                escape_markdown(str(entry.get("name") or "")),
                                str(entry.get("count") or 0),
                            )
                            for entry in results_summary.top_source_files
                        ),
                    )
                ),
                "",
            ])

    index_lines.extend([
        "## Targets",
        "",
    ])
    index_lines.append(
        render_markdown_table(
            Table(
                headers=("Target", "Path", "Exit", "Results", "Failed"),
                rows=_target_summary_rows(targets),
            )
        )
    )
    index_lines.append("")

    index_path = markdown_bundle_index(root)
    index_path.write_text("\n".join(index_lines), encoding="utf-8")
    return str(index_path)
