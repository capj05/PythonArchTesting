"""Single-target Markdown renderers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from ..ir.models import ReportDocument
from ..presentation import (
    MarkdownMode,
    build_run_presentation,
    build_target_presentation,
)
from .escape import escape_markdown
from .markdown_sections import (
    render_debug_appendices,
    render_standard_target_sections,
    render_target_detail_sections,
)


def render_markdown_mode(
    document: ReportDocument,
    *,
    mode: MarkdownMode,
    matching_debug_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Render a single-target markdown document for an explicit internal mode."""
    if mode not in {"verbose", "debug"}:
        raise ValueError(
            f"Unsupported internal single-target markdown mode '{mode}'. "
            "Only 'verbose' and 'debug' are implemented."
        )

    target = document.targets[0]
    run_presentation = build_run_presentation(document, mode=mode)
    target_presentation = build_target_presentation(target, mode=mode)
    lines: List[str] = [
        f"# {escape_markdown(run_presentation.title)}",
        "",
        f"**Generated:** {escape_markdown(str(document.generated_at))}",
        f"**Framework:** {escape_markdown(str(document.framework_version))}",
        f"**Exit Code:** {document.exit_code}",
        "",
    ]
    lines.extend(render_target_detail_sections(target, target_presentation))
    if mode == "debug":
        lines.extend(
            render_debug_appendices(
                target,
                target_presentation,
                matching_debug_context=matching_debug_context,
                target_path=document.run.target_path,
            )
        )
    return "\n".join(lines)


def render_markdown(
    document: ReportDocument,
    *,
    matching_debug_context: Optional[Dict[str, Any]] = None,
    markdown_mode: str = "standard",
) -> str:
    """Render typed single-target report document in markdown format."""
    if markdown_mode != "standard":
        return render_markdown_mode(
            document,
            mode=cast(MarkdownMode, markdown_mode),
            matching_debug_context=matching_debug_context,
        )
    target = document.targets[0]
    run_presentation = build_run_presentation(document, mode="standard")
    target_presentation = build_target_presentation(target, mode="standard")

    lines: List[str] = [
        f"# {escape_markdown(run_presentation.title)}",
        "",
        f"**Generated:** {escape_markdown(str(document.generated_at))}",
        f"**Framework:** {escape_markdown(str(document.framework_version))}",
        f"**Exit Code:** {document.exit_code}",
        "",
    ]
    lines.extend(
        render_standard_target_sections(
            target,
            target_presentation,
            hotspots=run_presentation.rule_hotspots,
        )
    )
    return "\n".join(lines)
