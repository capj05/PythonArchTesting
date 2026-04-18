from datetime import datetime, timezone
from pathlib import Path

import pytest

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.exceptions import ReportGenerationError
from pythonarchtesting.report.api import build_multi_target_report
from pythonarchtesting.report.ir.builder import build_multi_target_report_ir
from pythonarchtesting.state import ValidationResult, ValidationStatus
from pythonarchtesting.state_multi import RunState, TargetRunState


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
        validation_scope="all",
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
