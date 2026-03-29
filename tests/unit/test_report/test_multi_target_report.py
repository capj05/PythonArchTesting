from datetime import datetime, timezone
from pathlib import Path

import pytest

import src.report.api as report_api
from src.config.data import create_config_from_dict
from src.entities import build_entity_index
from src.exceptions import ReportGenerationError
from src.matching import MatchResult, MatchStatus
from src.report.api import build_multi_target_report
from src.state import ValidationResult, ValidationStatus
from src.state_multi import RunState, TargetRunState


def _cfg(report: dict | None = None):
    return create_config_from_dict({"report": report or {}})


def _empty_run_state(cfg, generated_at: datetime) -> RunState:
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
        run_generated_at=generated_at,
        framework_version="test",
    )


def _target_state(
    target_id: str,
    target_path: Path,
    *,
    match_results=None,
    validation_results=None,
) -> TargetRunState:
    empty_index = build_entity_index([])
    return TargetRunState(
        target_id=target_id,
        target_path=target_path,
        target_entities=[],
        target_index=empty_index,
        target_by_id={},
        match_results=match_results or [],
        match_by_source={},
        rule_results=[],
        validation_results=validation_results or [],
    )


def test_multi_target_json_schema_v2_fields_and_sorted_targets(tmp_path):
    cfg = _cfg()
    generated_at = datetime(2026, 2, 12, 12, 0, 0, tzinfo=timezone.utc)
    run_state = _empty_run_state(cfg, generated_at)

    failing = ValidationResult(
        status=ValidationStatus.FAILED,
        description="fail",
        check_type="arch/fail",
        src_function_name="src",
        src_package="pkg",
        details={},
        project_name="b",
    )

    target_b = _target_state("b", tmp_path / "b", validation_results=[failing])
    target_a = _target_state("a", tmp_path / "a")

    report = build_multi_target_report(run_state, [target_b, target_a], cfg)

    assert report["schema_version"] == "2"
    assert "run" in report
    assert "targets" in report
    assert "summary" in report
    assert "exit_code" in report
    assert [t["target_id"] for t in report["targets"]] == ["a", "b"]
    assert report["run"]["mode"] == "static-only"
    assert report["targets"][1]["exit_code"] == 1
    assert report["exit_code"] == 1


def test_multi_target_generated_at_uses_run_state_timestamp(tmp_path):
    cfg = _cfg()
    generated_at = datetime(2026, 2, 12, 8, 30, 0, tzinfo=timezone.utc)
    run_state = _empty_run_state(cfg, generated_at)

    report = build_multi_target_report(
        run_state, [_target_state("a", tmp_path / "a")], cfg
    )
    expected = generated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    assert report["generated_at"] == expected


def test_multi_target_config_snapshot_optional(tmp_path):
    cfg = _cfg()
    run_state = _empty_run_state(cfg, datetime.now(timezone.utc))

    report = build_multi_target_report(
        run_state, [_target_state("a", tmp_path / "a")], cfg
    )
    assert report["run"]["config_snapshot"] is None

    cfg = _cfg({"include_config_snapshot": True})
    run_state = _empty_run_state(cfg, datetime.now(timezone.utc))
    report_with_snapshot = build_multi_target_report(
        run_state, [_target_state("a", tmp_path / "a")], cfg
    )
    assert report_with_snapshot["run"]["config_snapshot"] is not None


def test_multi_target_matching_isolated(tmp_path):
    cfg = _cfg()
    run_state = _empty_run_state(cfg, datetime.now(timezone.utc))

    match_a = MatchResult(
        source_id="s1",
        status=MatchStatus.MATCHED,
        target_id="t1",
        confidence=1.0,
        reasons=[],
        candidates=[],
    )
    match_b = MatchResult(
        source_id="s2",
        status=MatchStatus.UNMATCHED,
        target_id=None,
        confidence=0.0,
        reasons=[],
        candidates=[],
    )

    target_a = _target_state("a", tmp_path / "a", match_results=[match_a])
    target_b = _target_state("b", tmp_path / "b", match_results=[match_b])

    report = build_multi_target_report(run_state, [target_b, target_a], cfg)
    targets = {t["target_id"]: t for t in report["targets"]}

    assert targets["a"]["matching"]["matches"][0]["source_entity_id"] == "s1"
    assert targets["b"]["matching"]["matches"][0]["source_entity_id"] == "s2"


def test_multi_target_schema_validation_toggle(tmp_path, monkeypatch):
    cfg = _cfg({"validate_schema_v2": True})
    run_state = _empty_run_state(cfg, datetime.now(timezone.utc))
    target_states = [_target_state("a", tmp_path / "a")]

    monkeypatch.setattr(report_api, "validate_report_schema_v2", lambda report: [])
    report = build_multi_target_report(run_state, target_states, cfg)
    assert report["schema_version"] == "2"

    monkeypatch.setattr(report_api, "validate_report_schema_v2", lambda report: ["bad"])
    with pytest.raises(ReportGenerationError):
        build_multi_target_report(run_state, target_states, cfg)


def test_multi_target_results_sorted(tmp_path):
    cfg = _cfg()
    run_state = _empty_run_state(cfg, datetime.now(timezone.utc))

    warning = ValidationResult(
        status=ValidationStatus.WARNING,
        description="warn",
        check_type="warn_rule",
        src_function_name="src",
        src_package="pkg",
        details={},
        project_name="a",
    )
    failing = ValidationResult(
        status=ValidationStatus.FAILED,
        description="fail",
        check_type="error_rule",
        src_function_name="src",
        src_package="pkg",
        details={},
        project_name="a",
    )

    target = _target_state(
        "a",
        tmp_path / "a",
        validation_results=[warning, failing],
    )

    report = build_multi_target_report(run_state, [target], cfg)
    results = report["targets"][0]["results"]
    assert [item["rule_id"] for item in results] == ["error_rule", "warn_rule"]
