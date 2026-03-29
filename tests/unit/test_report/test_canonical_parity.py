from datetime import datetime, timezone
from pathlib import Path

import pytest

import src.report.api as report_api
import src.report.core as report_core
from src.config.data import create_config_from_dict
from src.entities import build_entity_index
from src.exceptions import ReportGenerationError
from src.report.api import build_multi_target_report, build_report
from src.state import ProjectState, ValidationResult, ValidationStatus
from src.state_multi import RunState, TargetRunState


def _state_with_results(tmp_path: Path) -> ProjectState:
    state = ProjectState(str(tmp_path), [])
    state.initialize(str(tmp_path))
    state.add_validation_result(
        ValidationResult(
            status=ValidationStatus.FAILED,
            description="fail",
            check_type="arch/forbidden_dependency",
            src_function_name="fn",
            src_package="pkg.a",
            src_file="a.py",
            src_line_num=3,
            target_function_name="t_fn",
            target_package="pkg.t",
            details={"duration": 0.25},
        )
    )
    return state


def test_single_report_has_canonical_required_fields(tmp_path):
    report = build_report(_state_with_results(tmp_path))
    assert isinstance(report.get("summary"), dict)
    assert report["run"]["mode"] == "static-only"
    assert report["summary"]["results_total"] == 1
    item = report["results"][0]
    for key in (
        "result_id",
        "project_id",
        "rule_id",
        "category",
        "severity",
        "status",
        "source",
        "target",
        "message",
        "evidence",
        "details",
        "locations",
    ):
        assert key in item
    assert item["timing_seconds"] == 0.25


def _mk_run_state(cfg):
    empty_index = build_entity_index([])
    return RunState(
        config=cfg,
        source_path=Path("/source"),
        reference_modules=[],
        source_entities=[],
        source_index=empty_index,
        source_by_id={},
        rules=[],
        compiler_results=[],
        compiler_validations=[],
        run_generated_at=datetime(2026, 2, 12, 10, 0, tzinfo=timezone.utc),
        framework_version="test",
    )


def _mk_target(target_id: str, failed: bool) -> TargetRunState:
    empty_index = build_entity_index([])
    return TargetRunState(
        target_id=target_id,
        target_path=Path(f"/targets/{target_id}"),
        target_entities=[],
        target_index=empty_index,
        target_by_id={},
        match_results=[],
        match_by_source={},
        rule_results=[],
        validation_results=[
            ValidationResult(
                status=(
                    ValidationStatus.FAILED if failed else ValidationStatus.OK
                ),  # noqa: E501
                description="x",
                check_type="arch/forbidden_dependency",
                src_function_name="fn",
                src_package="pkg",
                details={},
                project_name=target_id,
            )
        ],
    )


def test_multi_report_summary_and_determinism():
    cfg = create_config_from_dict({})
    run_state = _mk_run_state(cfg)
    targets = [_mk_target("b", True), _mk_target("a", False)]
    first = build_multi_target_report(run_state, targets, cfg)
    second = build_multi_target_report(run_state, targets, cfg)

    assert first == second
    assert [t["target_id"] for t in first["targets"]] == ["a", "b"]
    assert first["summary"]["results"]["results_total"] == 2
    assert first["summary"]["targets_total"] == 2
    assert first["summary"]["targets_failed"] == 1


def test_report_core_and_api_single_report_parity(tmp_path, monkeypatch):
    cfg = create_config_from_dict({})
    state = _state_with_results(tmp_path)

    fixed_now = "2026-02-12T00:00:00Z"
    monkeypatch.setattr(report_api, "now_utc_z", lambda: fixed_now)
    monkeypatch.setattr(report_core, "now_utc_z", lambda: fixed_now)

    api_report = report_api.build_report(state, cfg)
    core_report = report_core.build_report(state, cfg)
    assert core_report == api_report


def test_report_core_and_api_multi_report_parity():
    cfg = create_config_from_dict({})
    run_state = _mk_run_state(cfg)
    targets = [_mk_target("b", True), _mk_target("a", False)]

    api_report = report_api.build_multi_target_report(  # noqa: E501
        run_state, targets, cfg
    )
    core_report = report_core.build_multi_target_report(  # noqa: E501
        run_state, targets, cfg
    )
    assert core_report == api_report


def test_report_core_wrapper_pushes_now_hook_into_api(tmp_path, monkeypatch):
    cfg = create_config_from_dict({})
    state = _state_with_results(tmp_path)
    monkeypatch.setattr(  # noqa: E501
        report_api, "now_utc_z", lambda: "2001-01-01T00:00:00Z"
    )
    monkeypatch.setattr(  # noqa: E501
        report_core, "now_utc_z", lambda: "2026-02-12T00:00:00Z"
    )

    report = report_core.build_report(state, cfg)
    assert report["generated_at"] == "2026-02-12T00:00:00Z"


def test_report_core_wrapper_pushes_schema_hook_into_api(  # noqa: E501
    tmp_path, monkeypatch
):
    cfg = create_config_from_dict({"report": {"validate_schema_v2": True}})
    state = _state_with_results(tmp_path)

    monkeypatch.setattr(
        report_core, "validate_report_schema_v2", lambda _report: ["bad"]
    )
    with pytest.raises(ReportGenerationError):
        report_core.build_report(state, cfg)
