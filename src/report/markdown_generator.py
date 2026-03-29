"""Markdown report generator for validation results."""

from pathlib import Path
from typing import Any

from .base_generator import BaseReportGenerator
from .renderers.markdown import render_markdown
from .renderers.markdown_multi import render_markdown_bundle


class MarkdownReportGenerator(BaseReportGenerator):
    """Generates Markdown reports from canonical report data."""

    def __init__(
        self,
        report_data: Any,
        matching_debug_context: dict | None = None,
    ) -> None:
        super().__init__(report_data)
        self._matching_debug_context = matching_debug_context

    def _generate_report(self, output_file: str | None = None) -> str:
        report = self._ensure_report()
        if (
            isinstance(report, dict)
            and report.get("targets") is not None
            and report.get("run")
        ):
            if report.get("results") is None and report.get("targets"):
                if not output_file:
                    raise ValueError(
                        "Multi-target markdown reporting requires an output directory path."
                    )
                return render_markdown_bundle(
                    report,
                    Path(output_file),
                    matching_debug_context=self._matching_debug_context,
                )
        return render_markdown(
            report, matching_debug_context=self._matching_debug_context
        )
