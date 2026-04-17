"""Markdown report generator for validation results."""

from pathlib import Path
from typing import Any

from .base_generator import BaseReportGenerator
from .presentation import MarkdownMode
from .renderers.markdown import render_markdown, render_markdown_mode
from .renderers.markdown_multi import (
    render_markdown_bundle,
    render_markdown_bundle_mode,
)


class MarkdownReportGenerator(BaseReportGenerator):
    """Generates Markdown reports from canonical report data."""

    def __init__(
        self,
        report_data: Any,
        matching_debug_context: dict | None = None,
        markdown_mode: MarkdownMode | None = None,
    ) -> None:
        super().__init__(report_data)
        self._matching_debug_context = matching_debug_context
        self._markdown_mode = markdown_mode

    def _generate_report(self, output_file: str | None = None) -> str:
        document = self._ensure_document()
        if document.kind == "multi":
            if not output_file:
                raise ValueError(
                    "Multi-target markdown reporting requires an output directory path."
                )
            if self._markdown_mode not in {None, "standard"}:
                return render_markdown_bundle_mode(
                    document,
                    Path(output_file),
                    mode=self._markdown_mode,
                    matching_debug_context=self._matching_debug_context,
                )
            return render_markdown_bundle(
                document,
                Path(output_file),
                matching_debug_context=self._matching_debug_context,
                markdown_mode=self._markdown_mode or "standard",
            )
        if self._markdown_mode not in {None, "standard"}:
            return render_markdown_mode(
                document,
                mode=self._markdown_mode,
                matching_debug_context=self._matching_debug_context,
            )
        return render_markdown(
            document,
            matching_debug_context=self._matching_debug_context,
            markdown_mode=self._markdown_mode or "standard",
        )
