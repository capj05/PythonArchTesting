from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.report.api import build_run_report_payload
from pythonarchtesting.report.ir.builder import build_run_report_ir
from pythonarchtesting.report.ir.serialize import to_legacy_schema_v2
from pythonarchtesting.run_state import RunState, TargetRunState
from pythonarchtesting.state import ValidationResult, ValidationStatus


def _cfg():
    return create_config_from_dict({"report": {}})


def _run_state(cfg) -> RunState:
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
        run_generated_at=datetime(2026, 2, 12, 9, 0, tzinfo=timezone.utc),
        framework_version="test",
    )


def _target(target_id: str, failed: bool) -> TargetRunState:
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


def test_build_run_report_ir_roundtrip():
    cfg = _cfg()
    run_state = _run_state(cfg)
    targets = [_target("b", True), _target("a", False)]

    doc = build_run_report_ir(run_state, targets, cfg)
    assert doc.kind == "run"
    assert [t.target_id for t in doc.targets] == ["a", "b"]
    assert doc.summary.targets_total == 2
    assert doc.run.mode == "static-only"

    assert to_legacy_schema_v2(doc) == build_run_report_payload(run_state, targets, cfg)
