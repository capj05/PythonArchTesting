"""Compatibility wrapper around the canonical report API."""

from __future__ import annotations

from contextlib import contextmanager
from types import ModuleType
from typing import Any, Dict, Iterator, List, Optional, cast

from src.constants import ReportingConstants
from src.state import ProjectState
from src.state_multi import RunState, TargetRunState

from .ir.from_state import now_utc_z
from .schema_v2 import validate_report_schema_v2 as _validate_report_schema_v2

# Monkeypatch-compatible hook aliases expected by existing tests/callers.
validate_report_schema_v2 = _validate_report_schema_v2


def _sync_api_hooks() -> None:
    from . import api as report_api

    report_api.now_utc_z = now_utc_z
    report_api.validate_report_schema_v2 = validate_report_schema_v2


@contextmanager
def _synced_api_hooks() -> Iterator[ModuleType]:
    from . import api as report_api

    previous_now = report_api.now_utc_z
    previous_validate = report_api.validate_report_schema_v2
    _sync_api_hooks()
    try:
        yield report_api
    finally:
        report_api.now_utc_z = previous_now
        report_api.validate_report_schema_v2 = previous_validate


def build_report(
    state_obj: ProjectState, config: Optional[Any] = None
) -> Dict[str, Any]:
    with _synced_api_hooks() as report_api:
        return cast(Dict[str, Any], report_api.build_report(state_obj, config))


def build_multi_target_report(
    run_state: RunState,
    target_states: List[TargetRunState],
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    with _synced_api_hooks() as report_api:
        return cast(
            Dict[str, Any],
            report_api.build_multi_target_report(run_state, target_states, config),
        )


def compute_exit_code(results: List[Dict[str, Any]], config: Any) -> int:
    with _synced_api_hooks() as report_api:
        return cast(int, report_api.compute_exit_code(results, config))


def compute_target_exit_code(results: List[Dict[str, Any]], config: Any) -> int:
    with _synced_api_hooks() as report_api:
        return cast(int, report_api.compute_target_exit_code(results, config))


def compute_aggregate_exit_code(
    target_states: List[TargetRunState], config: Any
) -> int:
    with _synced_api_hooks() as report_api:
        return cast(int, report_api.compute_aggregate_exit_code(target_states, config))


def generate_multi_target_report(
    run_state: RunState,
    target_states: List[TargetRunState],
    output_format: str = ReportingConstants.JSON_FORMAT,
    config: Optional[Any] = None,
) -> str:
    with _synced_api_hooks() as report_api:
        return cast(
            str,
            report_api.generate_multi_target_report(
                run_state,
                target_states,
                output_format=output_format,
                config=config,
                output_path=None,
            ),
        )


def get_multi_exit_code(
    run_state: RunState,
    target_states: List[TargetRunState],
    config: Optional[Any] = None,
) -> int:
    with _synced_api_hooks() as report_api:
        return cast(
            int, report_api.get_multi_exit_code(run_state, target_states, config)
        )


def generate_validation_report(
    state_obj: ProjectState,
    output_format: str = ReportingConstants.JSON_FORMAT,
    include_sections: Optional[List[str]] = None,
    config: Optional[Any] = None,
) -> str:
    with _synced_api_hooks() as report_api:
        return cast(
            str,
            report_api.generate_validation_report(
                state_obj,
                output_format=output_format,
                include_sections=include_sections,
                config=config,
            ),
        )
