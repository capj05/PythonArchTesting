"""Internal renderer protocol definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, Tuple

from pythonarchtesting.report.ir.models import ReportDocument


@dataclass(frozen=True, slots=True)
class RenderOptions:
    """Options shared by all renderer implementations."""

    include_sections: Tuple[str, ...] = ()
    max_evidence_items_text: int = 3
    output_path: Optional[Path] = None


class IRGenerator(Protocol):
    """Protocol for format-specific IR renderers."""

    sink: str

    def generate(self, doc: ReportDocument, options: RenderOptions) -> str:
        """Generate sink output from the report document."""
        ...
