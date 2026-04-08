"""JSON report generator for validation results."""

from typing import Optional

from .base_generator import BaseReportGenerator
from .renderers.json import render_json


class JSONReportGenerator(BaseReportGenerator):
    """Generates JSON reports for validation results."""

    def _generate_report(self, output_file: Optional[str] = None) -> str:
        rendered = render_json(self._ensure_document())
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(rendered)
        return rendered
