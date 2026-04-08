"""Canonical reporting API built on the canonical schema-v2 report model."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pythonarchtesting.constants import ReportingConstants
from pythonarchtesting.exceptions import ReportGenerationError
from pythonarchtesting.state import ProjectState
from pythonarchtesting.state_multi import RunState, TargetRunState

from .dispatcher import create_reporter
from .ir.from_state import (
    build_multi_target_report_document as _build_multi_target_report_document_from_state,
)
from .ir.from_state import build_report_document as _build_report_document_from_state
from .ir.from_state import (
    now_utc_z,
)
from .ir.models import ReportDocument
from .ir.serialize import to_legacy_schema_v2
from .policy import compute_aggregate_exit_code as _compute_aggregate_exit_code
from .policy import compute_exit_code as _compute_exit_code
from .policy import compute_target_exit_code as _compute_target_exit_code
from .renderers import render_json
from .schema_v2 import validate_report_schema_v2 as _validate_report_schema_v2

validate_report_schema_v2 = _validate_report_schema_v2


def build_report_document(
    state_obj: ProjectState, config: Optional[Any] = None
) -> ReportDocument:
    """Build typed single-target report IR document."""
    return _build_report_document_from_state(
        state_obj,
        config,
        now_utc_z_fn=now_utc_z,
        validate_report_schema_v2_fn=validate_report_schema_v2,
    )


def build_multi_target_report_document(
    run_state: RunState,
    target_states: Sequence[TargetRunState],
    config: Optional[Any] = None,
) -> ReportDocument:
    """Build typed multi-target report IR document."""
    return _build_multi_target_report_document_from_state(
        run_state,
        list(target_states),
        config,
        validate_report_schema_v2_fn=validate_report_schema_v2,
    )


def build_report(
    state_obj: ProjectState, config: Optional[Any] = None
) -> Dict[str, Any]:
    """Build canonical schema-v2 report dictionary for single-target runs."""
    return to_legacy_schema_v2(build_report_document(state_obj, config))


def build_multi_target_report(
    run_state: RunState,
    target_states: Sequence[TargetRunState],
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build canonical schema-v2 report dictionary for multi-target runs."""
    return to_legacy_schema_v2(
        build_multi_target_report_document(run_state, target_states, config)
    )


def build_run_report(
    run_state: RunState,
    target_states: Sequence[TargetRunState],
    config: Optional[Any] = None,
) -> ReportDocument:
    """Canonical multi-target typed report builder."""
    return build_multi_target_report_document(run_state, target_states, config)


def generate_validation_report(
    state_obj: ProjectState,
    output_format: str = ReportingConstants.JSON_FORMAT,
    include_sections: Optional[List[str]] = None,
    config: Optional[Any] = None,
) -> str:
    """
    Generate a report of validation results for a single target.

    Keeps compatibility with the existing dispatcher/generator interface.
    """
    if include_sections is None:
        include_sections = []

    try:
        normalized_format = output_format
        report_data: Any = state_obj
        if config is not None:
            report_data = build_report(state_obj, config)
        reporter_kwargs: Dict[str, Any] = {}
        if normalized_format == ReportingConstants.MARKDOWN_FORMAT:
            from .renderers.matching_debug import build_single_matching_debug_context

            reporter_kwargs["matching_debug_context"] = (
                build_single_matching_debug_context(state_obj)
            )
        reporter = create_reporter(normalized_format, report_data, **reporter_kwargs)
        return reporter.generate(include_sections=include_sections)
    except ValueError as e:
        raise ReportGenerationError(
            f"Unsupported output format '{output_format}'. "
            f"Available formats: json, markdown"
        ) from e


def generate_multi_target_report(
    run_state: RunState,
    target_states: List[TargetRunState],
    output_format: str = ReportingConstants.JSON_FORMAT,
    config: Optional[Any] = None,
    output_path: Optional[str | Path] = None,
) -> str:
    """Generate a multi-target report output for any registered sink."""
    report_data = build_multi_target_report(run_state, target_states, config)
    normalized_format = output_format
    if normalized_format == ReportingConstants.JSON_FORMAT:
        rendered = render_json(report_data)
        if output_path is not None:
            Path(output_path).write_text(rendered, encoding="utf-8")
        return rendered
    try:
        reporter_kwargs: Dict[str, Any] = {}
        if normalized_format == ReportingConstants.MARKDOWN_FORMAT:
            from .renderers.matching_debug import build_multi_matching_debug_context

            reporter_kwargs["matching_debug_context"] = (
                build_multi_matching_debug_context(run_state, target_states)
            )
        reporter = create_reporter(normalized_format, report_data, **reporter_kwargs)
        return reporter.generate(output_file=str(output_path) if output_path else None)
    except ValueError as e:
        raise ReportGenerationError(
            f"Unsupported multi-target format '{output_format}'. "
            f"Available formats: json, markdown"
        ) from e


def get_multi_exit_code(
    run_state: RunState,
    target_states: List[TargetRunState],
    config: Optional[Any] = None,
) -> int:
    """Get aggregate exit code for a multi-target run."""
    report = build_multi_target_report(run_state, target_states, config)
    return int(report.get("exit_code", 0))


def compute_exit_code(results: List[Dict[str, Any]], config: Any) -> int:
    """Compatibility shim for existing exit code policy behavior."""
    return _compute_exit_code(results, config)


def compute_target_exit_code(results: List[Dict[str, Any]], config: Any) -> int:
    """Compatibility shim for target-level exit code behavior."""
    return _compute_target_exit_code(results, config)


def compute_aggregate_exit_code(
    target_states: List[TargetRunState], config: Any
) -> int:
    """Compatibility shim for aggregate multi-target exit policy behavior."""
    return _compute_aggregate_exit_code(target_states, config)
