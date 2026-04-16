"""Canonical reporting API built on the canonical schema-v2 report model."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pythonarchtesting.constants import ReportingConstants
from pythonarchtesting.exceptions import ReportGenerationError
from pythonarchtesting.state import ProjectState
from pythonarchtesting.state_multi import RunState, TargetRunState

from .ir import from_state as from_state_ir
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
from .renderers import render_json, render_markdown
from .renderers.markdown_multi import render_markdown_bundle
from .schema_v2 import validate_report_schema_v2 as _validate_report_schema_v2

validate_report_schema_v2 = _validate_report_schema_v2


def resolve_markdown_mode(config: Any | None, explicit_mode: str | None = None) -> str:
    """Resolve the effective markdown mode from explicit arg or config, defaulting to standard."""
    if explicit_mode is not None:
        return explicit_mode
    if config is None:
        return "standard"
    report_config = getattr(config, "report", None)
    return getattr(report_config, "markdown_mode", None) or "standard"


def build_report_document(
    state_obj: ProjectState,
    config: Optional[Any] = None,
    *,
    now_utc_z_fn: Any = None,
    validate_report_schema_v2_fn: Any = None,
) -> ReportDocument:
    """Build typed single-target report IR document."""
    return _build_report_document_from_state(
        state_obj,
        config,
        now_utc_z_fn=now_utc_z if now_utc_z_fn is None else now_utc_z_fn,
        validate_report_schema_v2_fn=(
            validate_report_schema_v2
            if validate_report_schema_v2_fn is None
            else validate_report_schema_v2_fn
        ),
    )


def build_multi_target_report_document(
    run_state: RunState,
    target_states: Sequence[TargetRunState],
    config: Optional[Any] = None,
    *,
    validate_report_schema_v2_fn: Any = None,
) -> ReportDocument:
    """Build typed multi-target report IR document."""
    return _build_multi_target_report_document_from_state(
        run_state,
        list(target_states),
        config,
        validate_report_schema_v2_fn=(
            validate_report_schema_v2
            if validate_report_schema_v2_fn is None
            else validate_report_schema_v2_fn
        ),
    )


def build_single_target_report_document_from_run_target(
    run_state: RunState,
    target_state: TargetRunState,
    config: Optional[Any] = None,
    *,
    now_utc_z_fn: Any = None,
    validate_report_schema_v2_fn: Any = None,
) -> ReportDocument:
    """Build typed single-target report IR from unified run/target state."""
    return from_state_ir.build_single_target_report_document_from_run_target(
        run_state,
        target_state,
        config,
        now_utc_z_fn=now_utc_z if now_utc_z_fn is None else now_utc_z_fn,
        validate_report_schema_v2_fn=(
            validate_report_schema_v2
            if validate_report_schema_v2_fn is None
            else validate_report_schema_v2_fn
        ),
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


def build_single_target_report_from_run_target(
    run_state: RunState,
    target_state: TargetRunState,
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build canonical schema-v2 report dictionary for unified single-target runs."""
    return to_legacy_schema_v2(
        build_single_target_report_document_from_run_target(
            run_state,
            target_state,
            config,
        )
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
    markdown_mode: Optional[str] = None,
) -> str:
    """Generate a report of validation results for a single target."""
    del include_sections
    try:
        document = build_report_document(state_obj, config)
        if output_format == ReportingConstants.JSON_FORMAT:
            return render_json(document)
        if output_format == ReportingConstants.MARKDOWN_FORMAT:
            from .renderers.matching_debug import build_single_matching_debug_context

            return render_markdown(
                document,
                matching_debug_context=build_single_matching_debug_context(state_obj),
                markdown_mode=resolve_markdown_mode(config, markdown_mode),
            )
        raise ValueError(output_format)
    except ValueError as e:
        raise ReportGenerationError(
            f"Unsupported output format '{output_format}'. "
            f"Available formats: json, markdown"
        ) from e


def generate_single_target_report_from_run_target(
    run_state: RunState,
    target_state: TargetRunState,
    output_format: str = ReportingConstants.JSON_FORMAT,
    config: Optional[Any] = None,
    markdown_mode: Optional[str] = None,
) -> str:
    """Generate a report of validation results for a unified single target."""
    try:
        document = build_single_target_report_document_from_run_target(
            run_state,
            target_state,
            config,
        )
        if output_format == ReportingConstants.JSON_FORMAT:
            return render_json(document)
        if output_format == ReportingConstants.MARKDOWN_FORMAT:
            from .renderers.matching_debug import build_multi_matching_debug_context

            return render_markdown(
                document,
                matching_debug_context=build_multi_matching_debug_context(
                    run_state, [target_state]
                ),
                markdown_mode=resolve_markdown_mode(config, markdown_mode),
            )
        raise ValueError(output_format)
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
    markdown_mode: Optional[str] = None,
) -> str:
    """Generate a multi-target report output for a supported format."""
    document = build_multi_target_report_document(run_state, target_states, config)
    if output_format == ReportingConstants.JSON_FORMAT:
        rendered = render_json(document)
        if output_path is not None:
            Path(output_path).write_text(rendered, encoding="utf-8")
        return rendered
    try:
        if output_format == ReportingConstants.MARKDOWN_FORMAT:
            from .renderers.matching_debug import build_multi_matching_debug_context

            if output_path is None:
                raise ValueError(
                    "Multi-target markdown reporting requires an output directory path."
                )
            return render_markdown_bundle(
                document,
                Path(output_path),
                matching_debug_context=build_multi_matching_debug_context(
                    run_state, target_states
                ),
                markdown_mode=resolve_markdown_mode(config, markdown_mode),
            )
        raise ValueError(output_format)
    except ValueError as e:
        if (
            str(e)
            == "Multi-target markdown reporting requires an output directory path."
        ):
            raise
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
