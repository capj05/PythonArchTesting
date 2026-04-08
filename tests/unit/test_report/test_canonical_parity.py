from datetime import datetime, timezone
from pathlib import Path

import pytest

import pythonarchtesting.report.core as report_core
from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.exceptions import ReportGenerationError
from pythonarchtesting.report.api import build_multi_target_report, build_report
from pythonarchtesting.report.ir.builder import (
    build_multi_target_report_ir,
    build_report_ir,
)
from pythonarchtesting.report.ir.serialize import to_legacy_schema_v2
from pythonarchtesting.state import ProjectState, ValidationResult, ValidationStatus
from pythonarchtesting.state_multi import RunState, TargetRunState


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
                status=ValidationStatus.FAILED if failed else ValidationStatus.OK,
                description="x",
                check_type="arch/forbidden_dependency",
                src_function_name="fn",
                src_package="pkg",
                details={},
                project_name=target_id,
            )
        ],
    )


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


def test_build_report_ir_injection_controls_generated_at(tmp_path):
    state = _state_with_results(tmp_path)

    document = build_report_ir(
        state,
        now_utc_z_fn=lambda: "2026-02-12T00:00:00Z",
    )

    assert document.generated_at == "2026-02-12T00:00:00Z"
    assert to_legacy_schema_v2(document)["generated_at"] == "2026-02-12T00:00:00Z"


def test_build_multi_target_report_ir_injection_uses_schema_validator():
    cfg = create_config_from_dict({"report": {"validate_schema_v2": True}})
    run_state = _mk_run_state(cfg)
    targets = [_mk_target("a", False)]

    with pytest.raises(ReportGenerationError):
        build_multi_target_report_ir(
            run_state,
            targets,
            cfg,
            validate_report_schema_v2_fn=lambda _report: ["bad"],
        )


def test_report_core_build_report_uses_explicit_hook_injection(tmp_path, monkeypatch):
    cfg = create_config_from_dict({})
    state = _state_with_results(tmp_path)
    monkeypatch.setattr(report_core, "now_utc_z", lambda: "2026-02-12T00:00:00Z")

    report = report_core.build_report(state, cfg)

    assert report["generated_at"] == "2026-02-12T00:00:00Z"


def test_report_core_build_report_uses_explicit_schema_validator(tmp_path, monkeypatch):
    cfg = create_config_from_dict({"report": {"validate_schema_v2": True}})
    state = _state_with_results(tmp_path)
    monkeypatch.setattr(report_core, "validate_report_schema_v2", lambda _report: ["bad"])

    with pytest.raises(ReportGenerationError):
        report_core.build_report(state, cfg)
