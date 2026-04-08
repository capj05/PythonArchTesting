import pytest

import pythonarchtesting.report.api as report_api
from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.core.models import RuleResult
from pythonarchtesting.entities import Entity, SignatureInfo
from pythonarchtesting.exceptions import ReportGenerationError
from pythonarchtesting.matching import Candidate, MatchResult, MatchStatus
from pythonarchtesting.report.api import (
    build_report,
    compute_aggregate_exit_code,
    compute_exit_code,
)
from pythonarchtesting.state import ProjectState, ValidationResult, ValidationStatus


def _fresh_state(tmp_path) -> ProjectState:
    state = ProjectState(str(tmp_path), [])
    state.initialize(str(tmp_path))
    return state


def test_build_report_deterministic(monkeypatch, tmp_path):
    state = _fresh_state(tmp_path)
    state.add_validation_result(
        ValidationResult(
            status=ValidationStatus.OK,
            description="ok",
            check_type="alpha",
            src_function_name="a_func",
            src_package="pkg_a",
            src_line_num=1,
            src_file="a.py",
            target_function_name="a_ref",
            target_package="ref_a",
            details={},
        )
    )
    state.add_validation_result(
        ValidationResult(
            status=ValidationStatus.WARNING,
            description="warn",
            check_type="beta",
            src_function_name="b_func",
            src_package="pkg_b",
            src_line_num=2,
            src_file="b.py",
            target_function_name="b_ref",
            target_package="ref_b",
            details={},
        )
    )

    monkeypatch.setattr(report_api, "now_utc_z", lambda: "2026-02-12T00:00:00Z")
    report1 = build_report(state)
    report2 = build_report(state)
    assert report1 == report2


def test_build_report_sorts_results(monkeypatch, tmp_path):
    state = _fresh_state(tmp_path)
    state.add_validation_result(
        ValidationResult(
            status=ValidationStatus.WARNING,
            description="warn",
            check_type="warn_rule",
            src_function_name="w_func",
            src_package="pkg_w",
            src_line_num=3,
            src_file="w.py",
            target_function_name="w_ref",
            target_package="ref_w",
            details={},
        )
    )
    state.add_validation_result(
        ValidationResult(
            status=ValidationStatus.FAILED,
            description="fail",
            check_type="error_rule",
            src_function_name="e_func",
            src_package="pkg_e",
            src_line_num=2,
            src_file="e.py",
            target_function_name="e_ref",
            target_package="ref_e",
            details={},
        )
    )
    state.add_validation_result(
        ValidationResult(
            status=ValidationStatus.OK,
            description="ok",
            check_type="info_rule",
            src_function_name="i_func",
            src_package="pkg_i",
            src_line_num=1,
            src_file="i.py",
            target_function_name="i_ref",
            target_package="ref_i",
            details={},
        )
    )

    monkeypatch.setattr(report_api, "now_utc_z", lambda: "2026-02-12T00:00:00Z")
    report = build_report(state)
    assert [item["rule_id"] for item in report["results"]] == [
        "error_rule",
        "warn_rule",
        "info_rule",
    ]


def test_build_report_missing_field_raises(tmp_path):
    class MissingField:
        status = ValidationStatus.OK
        check_type = "alpha"
        description = "missing"
        target_function_name = None
        target_package = None
        details = {}
        timestamp = 0.0

    state = _fresh_state(tmp_path)
    state.validation_results.append(MissingField())
    with pytest.raises(ReportGenerationError):
        build_report(state)


class _DummyConfig:
    def __init__(self, warnings_as_fail: bool) -> None:
        self._warnings_as_fail = warnings_as_fail

    def getboolean(self, section: str, key: str, default=None):
        if section == "report" and key == "warnings_as_fail":
            return self._warnings_as_fail
        return default


def test_compute_exit_code_warnings_as_fail():
    results = [
        {"status": "WARNING", "severity": "warning"},
        {"status": "SKIPPED", "severity": "warning"},
    ]
    assert compute_exit_code(results, _DummyConfig(False)) == 0
    assert compute_exit_code(results, _DummyConfig(True)) == 1


class _ExitState:
    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code


def test_compute_aggregate_exit_code_policies():
    targets = [_ExitState(1), _ExitState(0)]

    cfg = create_config_from_dict({"report": {"multi_target_exit_policy": "any_fail"}})
    assert compute_aggregate_exit_code(targets, cfg) == 1

    cfg = create_config_from_dict({"report": {"multi_target_exit_policy": "all_fail"}})
    assert compute_aggregate_exit_code(targets, cfg) == 0
    assert compute_aggregate_exit_code([_ExitState(1), _ExitState(1)], cfg) == 1

    cfg = create_config_from_dict(
        {"report": {"multi_target_exit_policy": "threshold", "fail_threshold": 2}}
    )
    assert compute_aggregate_exit_code(targets, cfg) == 0
    assert compute_aggregate_exit_code([_ExitState(1), _ExitState(1)], cfg) == 1


def test_matching_section_sorted_by_source_id(tmp_path):
    state = _fresh_state(tmp_path)
    state.match_results = [
        MatchResult(
            source_id="b",
            status=MatchStatus.MATCHED,
            target_id="t2",
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
        MatchResult(
            source_id="a",
            status=MatchStatus.MATCHED,
            target_id="t1",
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    ]

    report = build_report(state)
    matches = report["matching"]["matches"]
    assert [m["source_entity_id"] for m in matches] == ["a", "b"]


def test_candidate_sorting_uses_rounded_confidence(tmp_path):
    state = _fresh_state(tmp_path)
    c1 = Candidate(
        target_id="t1",
        confidence=0.1234564,
        breakdown={"module_distance": 1.0},
        tie_break=(),
    )
    c2 = Candidate(
        target_id="t2",
        confidence=0.1234563,
        breakdown={"module_distance": 2.0},
        tie_break=(),
    )
    state.match_results = [
        MatchResult(
            source_id="a",
            status=MatchStatus.MATCHED,
            target_id="t1",
            confidence=1.0,
            reasons=[],
            candidates=[c2, c1],
        )
    ]

    report = build_report(state)
    candidates = report["matching"]["matches"][0]["candidates"]
    assert candidates[0]["confidence"] == candidates[1]["confidence"] == 0.123456
    assert candidates[0]["target_entity_id"] == "t1"


def test_build_report_includes_config_snapshot_when_enabled(tmp_path):
    cfg = create_config_from_dict({"report": {"include_config_snapshot": True}})

    state = _fresh_state(tmp_path)
    state.add_validation_result(
        ValidationResult(
            status=ValidationStatus.OK,
            description="ok",
            check_type="alpha",
            src_function_name="a_func",
            src_package="pkg_a",
            src_line_num=1,
            src_file="a.py",
            target_function_name="a_ref",
            target_package="ref_a",
            details={},
        )
    )

    report = build_report(state, cfg)
    assert report["run"]["config_snapshot"] is not None


def test_build_report_schema_validation_toggle(tmp_path, monkeypatch):
    cfg = create_config_from_dict({"report": {"validate_schema_v2": True}})

    state = _fresh_state(tmp_path)
    state.add_validation_result(
        ValidationResult(
            status=ValidationStatus.OK,
            description="ok",
            check_type="alpha",
            src_function_name="a_func",
            src_package="pkg_a",
            src_line_num=1,
            src_file="a.py",
            target_function_name="a_ref",
            target_package="ref_a",
            details={},
        )
    )

    monkeypatch.setattr(report_api, "validate_report_schema_v2", lambda report: [])
    report = build_report(state, cfg)
    assert report["schema_version"] == "2"

    monkeypatch.setattr(report_api, "validate_report_schema_v2", lambda report: ["bad"])
    with pytest.raises(ReportGenerationError):
        build_report(state, cfg)


def test_build_report_dedupes_validation_results_with_explicit_ids(tmp_path):
    state = _fresh_state(tmp_path)

    source_entity = Entity(
        role="source",
        kind="function",
        root_label="source",
        module_path="pkg",
        qualname="func",
        name="func",
        filepath_rel="a.py",
        lineno=1,
        signature=SignatureInfo(0, 0, False, 0, False, 0, 0),
        signature_key="p0-a0-v0-k0-w0-d0-kd0",
        ast_fingerprint="",
        source_hash="",
        doc_hash=None,
        decorators_meta={},
        canonical_id="source:source:pkg:func:function:p0-a0-v0-k0-w0-d0-kd0",
        annotation_declarations=[],
        extras={},
    )
    target_entity = Entity(
        role="target",
        kind="function",
        root_label="target",
        module_path="pkg",
        qualname="func",
        name="func",
        filepath_rel="b.py",
        lineno=2,
        signature=SignatureInfo(0, 0, False, 0, False, 0, 0),
        signature_key="p0-a0-v0-k0-w0-d0-kd0",
        ast_fingerprint="",
        source_hash="",
        doc_hash=None,
        decorators_meta={},
        canonical_id="target:target:pkg:func:function:p0-a0-v0-k0-w0-d0-kd0",
        annotation_declarations=[],
        extras={},
    )

    state.source_by_id = {source_entity.canonical_id: source_entity}
    state.target_by_id = {target_entity.canonical_id: target_entity}

    rule_result = RuleResult(
        rule_id="rule/test",
        status="FAILED",
        source_entity_id=source_entity.canonical_id,
        target_entity_id=target_entity.canonical_id,
        match_status="matched",
        confidence=1.0,
        message="fail",
        evidence=(),
        details={"rule_id": "rule/test"},
    )
    state.rule_results = [rule_result]

    state.add_validation_result(
        ValidationResult(
            status=ValidationStatus.FAILED,
            description="fail",
            check_type="rule/test",
            src_function_name="func",
            src_package="pkg",
            details={
                "rule_id": "rule/test",
                "source_entity_id": source_entity.canonical_id,
                "target_entity_id": target_entity.canonical_id,
            },
        )
    )

    report = build_report(state)
    assert len(report["results"]) == 1


def test_build_report_hides_target_display_for_low_confidence_match(tmp_path):
    state = _fresh_state(tmp_path)

    source_entity = Entity(
        role="source",
        kind="method",
        root_label="source",
        module_path="calculator",
        qualname="Calculator.add",
        name="add",
        filepath_rel="calculator.py",
        lineno=38,
        signature=SignatureInfo(0, 0, False, 0, False, 0, 0),
        signature_key="p0-a0-v0-k0-w0-d0-kd0",
        ast_fingerprint="",
        source_hash="",
        doc_hash=None,
        decorators_meta={},
        canonical_id="source:source:calculator:Calculator.add:method:p0-a0-v0-k0-w0-d0-kd0",
        annotation_declarations=[],
        extras={},
    )
    target_entity = Entity(
        role="target",
        kind="method",
        root_label="target",
        module_path="calculator",
        qualname="Calculator.division",
        name="division",
        filepath_rel="calculator.py",
        lineno=55,
        signature=SignatureInfo(0, 0, False, 0, False, 0, 0),
        signature_key="p0-a0-v0-k0-w0-d0-kd0",
        ast_fingerprint="",
        source_hash="",
        doc_hash=None,
        decorators_meta={},
        canonical_id="target:target:calculator:Calculator.division:method:p0-a0-v0-k0-w0-d0-kd0",
        annotation_declarations=[],
        extras={},
    )

    state.source_by_id = {source_entity.canonical_id: source_entity}
    state.target_by_id = {target_entity.canonical_id: target_entity}
    state.rule_results = [
        RuleResult(
            rule_id="API002/required_method/v1",
            status="FAILED",
            source_entity_id=source_entity.canonical_id,
            target_entity_id=target_entity.canonical_id,
            match_status="low_confidence",
            confidence=0.732099,
            message="Required target entity missing or not matchable.",
            evidence=(),
            details={"reason": "required_target_missing"},
        )
    ]

    report = build_report(state)
    assert len(report["results"]) == 1
    row = report["results"][0]
    assert row["match_status"] == "low_confidence"
    assert row["target_entity_id"] == target_entity.canonical_id
    assert row["target"] == {
        "module": None,
        "qualname": None,
        "file": None,
        "line": None,
    }
