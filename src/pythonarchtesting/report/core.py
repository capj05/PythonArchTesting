"""Compatibility wrapper around the canonical report API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pythonarchtesting.constants import ReportingConstants
from pythonarchtesting.exceptions import ReportGenerationError
from pythonarchtesting.state import ProjectState
from pythonarchtesting.state_multi import RunState, TargetRunState

from . import api as report_api
from .ir.from_state import now_utc_z
from .ir.models import ReportDocument
from .ir.serialize import to_legacy_schema_v2
from .renderers import render_json, render_markdown
from .schema_v2 import validate_report_schema_v2 as _validate_report_schema_v2

# Monkeypatch-compatible hook aliases expected by existing tests/callers.
validate_report_schema_v2 = _validate_report_schema_v2


def build_report(
    state_obj: ProjectState, config: Optional[Any] = None
) -> Dict[str, Any]:
    document = report_api.build_report_document(
        state_obj,
        config,
        now_utc_z_fn=now_utc_z,
        validate_report_schema_v2_fn=validate_report_schema_v2,
    )
    return to_legacy_schema_v2(document)


def build_multi_target_report(
    run_state: RunState,
    target_states: List[TargetRunState],
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    document = report_api.build_multi_target_report_document(
        run_state,
        target_states,
        config,
        validate_report_schema_v2_fn=validate_report_schema_v2,
    )
    return to_legacy_schema_v2(document)


def build_single_target_report_document_from_run_target(
    run_state: RunState,
    target_state: TargetRunState,
    config: Optional[Any] = None,
) -> ReportDocument:
    return report_api.build_single_target_report_document_from_run_target(
        run_state,
        target_state,
        config,
        now_utc_z_fn=now_utc_z,
        validate_report_schema_v2_fn=validate_report_schema_v2,
    )


def build_single_target_report_from_run_target(
    run_state: RunState,
    target_state: TargetRunState,
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    document = build_single_target_report_document_from_run_target(
        run_state,
        target_state,
        config,
    )
    return to_legacy_schema_v2(document)


def compute_exit_code(results: List[Dict[str, Any]], config: Any) -> int:
    return report_api.compute_exit_code(results, config)


def compute_target_exit_code(results: List[Dict[str, Any]], config: Any) -> int:
    return report_api.compute_target_exit_code(results, config)


def compute_aggregate_exit_code(
    target_states: List[TargetRunState], config: Any
) -> int:
    return report_api.compute_aggregate_exit_code(target_states, config)


def generate_multi_target_report(
    run_state: RunState,
    target_states: List[TargetRunState],
    output_format: str = ReportingConstants.JSON_FORMAT,
    config: Optional[Any] = None,
) -> str:
    document = report_api.build_multi_target_report_document(
        run_state,
        target_states,
        config,
        validate_report_schema_v2_fn=validate_report_schema_v2,
    )
    if output_format == ReportingConstants.JSON_FORMAT:
        return render_json(document)
    if output_format == ReportingConstants.MARKDOWN_FORMAT:
        raise ValueError(
            "Multi-target markdown reporting requires an output directory path."
        )
    raise ReportGenerationError(
        f"Unsupported multi-target format '{output_format}'. "
        f"Available formats: json, markdown"
    )


def get_multi_exit_code(
    run_state: RunState,
    target_states: List[TargetRunState],
    config: Optional[Any] = None,
) -> int:
    document = report_api.build_multi_target_report_document(
        run_state,
        target_states,
        config,
        validate_report_schema_v2_fn=validate_report_schema_v2,
    )
    return document.exit_code


def generate_validation_report(
    state_obj: ProjectState,
    output_format: str = ReportingConstants.JSON_FORMAT,
    include_sections: Optional[List[str]] = None,
    config: Optional[Any] = None,
) -> str:
    del include_sections
    document = report_api.build_report_document(
        state_obj,
        config,
        now_utc_z_fn=now_utc_z,
        validate_report_schema_v2_fn=validate_report_schema_v2,
    )
    if output_format == ReportingConstants.JSON_FORMAT:
        return render_json(document)
    if output_format == ReportingConstants.MARKDOWN_FORMAT:
        from .renderers.matching_debug import build_single_matching_debug_context

        return render_markdown(
            document,
            matching_debug_context=build_single_matching_debug_context(state_obj),
        )
    raise ReportGenerationError(
        f"Unsupported output format '{output_format}'. "
        f"Available formats: json, markdown"
    )


def generate_single_target_report_from_run_target(
    run_state: RunState,
    target_state: TargetRunState,
    output_format: str = ReportingConstants.JSON_FORMAT,
    config: Optional[Any] = None,
) -> str:
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
        )
    raise ReportGenerationError(
        f"Unsupported output format '{output_format}'. "
        f"Available formats: json, markdown"
    )
