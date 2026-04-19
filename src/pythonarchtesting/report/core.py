"""Compatibility wrapper around the canonical report API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pythonarchtesting.constants import ReportingConstants
from pythonarchtesting.exceptions import ReportGenerationError
from pythonarchtesting.run_state import RunState, TargetRunState

from . import api as report_api
from .ir.serialize import to_legacy_schema_v2
from .renderers import render_json
from .schema_v2 import validate_report_schema_v2 as _validate_report_schema_v2

# Monkeypatch-compatible hook aliases expected by existing tests/callers.
validate_report_schema_v2 = _validate_report_schema_v2


def build_run_report_payload(
    run_state: RunState,
    target_states: List[TargetRunState],
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    document = report_api.build_run_report_document(
        run_state,
        target_states,
        config,
        validate_report_schema_v2_fn=validate_report_schema_v2,
    )
    return to_legacy_schema_v2(document)


def compute_target_exit_code(results: List[Dict[str, Any]], config: Any) -> int:
    return report_api.compute_target_exit_code(results, config)


def compute_aggregate_exit_code(
    target_states: List[TargetRunState], config: Any
) -> int:
    return report_api.compute_aggregate_exit_code(target_states, config)


def generate_run_report(
    run_state: RunState,
    target_states: List[TargetRunState],
    output_format: str = ReportingConstants.JSON_FORMAT,
    config: Optional[Any] = None,
) -> str:
    document = report_api.build_run_report_document(
        run_state,
        target_states,
        config,
        validate_report_schema_v2_fn=validate_report_schema_v2,
    )
    if output_format == ReportingConstants.JSON_FORMAT:
        return render_json(document)
    if output_format == ReportingConstants.MARKDOWN_FORMAT:
        raise ValueError("Markdown bundle reporting requires an output directory path.")
    raise ReportGenerationError(
        f"Unsupported run report format '{output_format}'. "
        f"Available formats: json, markdown"
    )


def get_run_exit_code(
    run_state: RunState,
    target_states: List[TargetRunState],
    config: Optional[Any] = None,
) -> int:
    document = report_api.build_run_report_document(
        run_state,
        target_states,
        config,
        validate_report_schema_v2_fn=validate_report_schema_v2,
    )
    return document.exit_code
