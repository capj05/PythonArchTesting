"""Markdown report generator for validation results."""

from pathlib import Path
from typing import Any

from .base_generator import BaseReportGenerator
from .renderers.markdown_bundle import render_markdown_bundle


class MarkdownReportGenerator(BaseReportGenerator):
    """Generates Markdown reports from canonical report data."""

    def __init__(
        self,
        report_data: Any,
        matching_debug_context: dict | None = None,
        detail: str = "verbose",
    ) -> None:
        super().__init__(report_data)
        self._matching_debug_context = matching_debug_context
        self._detail = detail

    def _generate_report(self, output_file: str | None = None) -> str:
        document = self._ensure_document()
        if not output_file:
            raise ValueError("Markdown reporting requires an output directory path.")
        return render_markdown_bundle(
            document,
            Path(output_file),
            matching_debug_context=self._matching_debug_context,
            detail=self._detail,
        )
