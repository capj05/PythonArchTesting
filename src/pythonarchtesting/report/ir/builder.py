"""IR builder for run execution state."""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from pythonarchtesting.run_state import RunState, TargetRunState

from ..schema_v2 import validate_report_schema_v2
from .from_state import build_run_report_document
from .models import ReportDocument


def build_run_report_ir(
    run_state: RunState,
    target_states: Sequence[TargetRunState],
    config: Optional[Any] = None,
    *,
    validate_report_schema_v2_fn: Callable[[Any], list[str]] = (
        validate_report_schema_v2
    ),
) -> ReportDocument:
    """Build typed IR for a run report."""
    return build_run_report_document(
        run_state,
        list(target_states),
        config,
        validate_report_schema_v2_fn=validate_report_schema_v2_fn,
    )
