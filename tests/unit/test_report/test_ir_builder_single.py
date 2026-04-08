from __future__ import annotations

from pythonarchtesting.report.api import build_report
from pythonarchtesting.report.ir.builder import build_report_ir
from pythonarchtesting.report.ir.serialize import to_legacy_schema_v2
from pythonarchtesting.state import ProjectState, ValidationResult, ValidationStatus


def _fresh_state(tmp_path) -> ProjectState:
    state = ProjectState(str(tmp_path), [])
    state.initialize(str(tmp_path))
    return state


def test_build_report_ir_single_roundtrip(tmp_path):
    state = _fresh_state(tmp_path)
    state.add_validation_result(
        ValidationResult(
            status=ValidationStatus.FAILED,
            description="fail",
            check_type="arch/fail",
            src_function_name="fn",
            src_package="pkg",
            src_file="a.py",
            src_line_num=2,
            target_function_name="t",
            target_package="ref",
            details={"duration": 0.5},
        )
    )

    doc = build_report_ir(state)
    assert doc.kind == "single"
    assert len(doc.targets) == 1
    assert doc.targets[0].results
    assert doc.targets[0].results[0].result_id
    assert doc.targets[0].results[0].stable_key

    rendered = to_legacy_schema_v2(doc)
    built = build_report(state)
    assert rendered["schema_version"] == built["schema_version"]
    assert rendered["results"] == built["results"]
    assert rendered["summary"] == built["summary"]
    assert rendered["exit_code"] == built["exit_code"]
