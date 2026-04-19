"""Canonical reporting API built on the canonical schema-v2 report model."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pythonarchtesting.constants import ReportingConstants
from pythonarchtesting.exceptions import ReportGenerationError
from pythonarchtesting.run_state import RunState, TargetRunState

from .ir.from_state import (
    build_run_report_document as _build_run_report_document_from_state,
)
from .ir.models import ReportDocument
from .ir.serialize import to_legacy_schema_v2
from .policy import compute_aggregate_exit_code as _compute_aggregate_exit_code
from .policy import compute_target_exit_code as _compute_target_exit_code
from .renderers import render_json
from .renderers.markdown_bundle import render_markdown_bundle
from .schema_v2 import validate_report_schema_v2 as _validate_report_schema_v2

validate_report_schema_v2 = _validate_report_schema_v2


def build_run_report_document(
    run_state: RunState,
    target_states: Sequence[TargetRunState],
    config: Optional[Any] = None,
    *,
    validate_report_schema_v2_fn: Any = None,
) -> ReportDocument:
    """Build the typed IR document for a run report."""
    return _build_run_report_document_from_state(
        run_state,
        list(target_states),
        config,
        validate_report_schema_v2_fn=(
            validate_report_schema_v2
            if validate_report_schema_v2_fn is None
            else validate_report_schema_v2_fn
        ),
    )


def build_run_report_payload(
    run_state: RunState,
    target_states: Sequence[TargetRunState],
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build the canonical schema-v2 payload for a run report."""
    return to_legacy_schema_v2(
        build_run_report_document(run_state, target_states, config)
    )


def build_run_report(
    run_state: RunState,
    target_states: Sequence[TargetRunState],
    config: Optional[Any] = None,
) -> ReportDocument:
    """Canonical typed run-report builder."""
    return build_run_report_document(run_state, target_states, config)


def generate_run_report(
    run_state: RunState,
    target_states: List[TargetRunState],
    output_format: str = ReportingConstants.JSON_FORMAT,
    config: Optional[Any] = None,
    output_path: Optional[str | Path] = None,
) -> str:
    """Generate a run report in a supported format."""
    document = build_run_report_document(run_state, target_states, config)
    if output_format == ReportingConstants.JSON_FORMAT:
        rendered = render_json(document)
        if output_path is not None:
            Path(output_path).write_text(rendered, encoding="utf-8")
        return rendered
    try:
        if output_format == ReportingConstants.MARKDOWN_FORMAT:
            from .renderers.matching_debug import build_run_matching_debug_context

            if output_path is None:
                raise ValueError(
                    "Markdown bundle reporting requires an output directory path."
                )
            return render_markdown_bundle(
                document,
                Path(output_path),
                matching_debug_context=build_run_matching_debug_context(
                    run_state, target_states
                ),
            )
        raise ValueError(output_format)
    except ValueError as e:
        if str(e) == "Markdown bundle reporting requires an output directory path.":
            raise
        raise ReportGenerationError(
            f"Unsupported run report format '{output_format}'. "
            f"Available formats: json, markdown"
        ) from e


def get_run_exit_code(
    run_state: RunState,
    target_states: List[TargetRunState],
    config: Optional[Any] = None,
) -> int:
    """Get the aggregate exit code for a run."""
    report = build_run_report_payload(run_state, target_states, config)
    return int(report.get("exit_code", 0))


def compute_target_exit_code(results: List[Dict[str, Any]], config: Any) -> int:
    """Compatibility shim for target-level exit code behavior."""
    return _compute_target_exit_code(results, config)


def compute_aggregate_exit_code(
    target_states: List[TargetRunState], config: Any
) -> int:
    """Compatibility shim for aggregate run exit policy behavior."""
    return _compute_aggregate_exit_code(target_states, config)
