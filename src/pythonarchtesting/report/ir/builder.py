"""IR builders from single-target and multi-target execution state."""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from pythonarchtesting.state import ProjectState
from pythonarchtesting.state_multi import RunState, TargetRunState

from ..schema_v2 import validate_report_schema_v2
from .from_state import (
    build_multi_target_report_document,
    build_report_document,
    now_utc_z,
)
from .models import ReportDocument


def build_report_ir(
    state_obj: ProjectState,
    config: Optional[Any] = None,
    *,
    now_utc_z_fn: Callable[[], str] = now_utc_z,
    validate_report_schema_v2_fn: Callable[[Any], list[str]] = (
        validate_report_schema_v2
    ),
) -> ReportDocument:
    """Build typed IR for a single-target run."""
    return build_report_document(
        state_obj,
        config,
        now_utc_z_fn=now_utc_z_fn,
        validate_report_schema_v2_fn=validate_report_schema_v2_fn,
    )


def build_multi_target_report_ir(
    run_state: RunState,
    target_states: Sequence[TargetRunState],
    config: Optional[Any] = None,
    *,
    validate_report_schema_v2_fn: Callable[[Any], list[str]] = (
        validate_report_schema_v2
    ),
) -> ReportDocument:
    """Build typed IR for a multi-target run."""
    return build_multi_target_report_document(
        run_state,
        list(target_states),
        config,
        validate_report_schema_v2_fn=validate_report_schema_v2_fn,
    )
