from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.infrastructure.logging import configure_logging
from pythonarchtesting.matching import MatchingConfig
from pythonarchtesting.report.api import build_multi_target_report
from pythonarchtesting.state_multi import RunState, TargetRunState


def _config():
    return create_config_from_dict(
        {
            "matching": {
                "threshold": "0.88",
                "max_stage2_candidates": "11",
                "max_stage3_candidates": "13",
            },
            "report": {"include_config_snapshot": "true"},
            "logging": {"level": "INFO", "filename": "integration.log", "file": "true"},
        }
    )


def test_config_propagates_matching_and_reporting_without_runtime_compat(
    monkeypatch, tmp_path
):
    cfg = _config()

    matching_cfg = MatchingConfig.from_config(cfg)
    assert matching_cfg.threshold == 0.88
    assert matching_cfg.max_stage2_candidates == 11
    assert matching_cfg.max_stage3_candidates == 13

    monkeypatch.chdir(tmp_path)
    configure_logging(cfg, force=True)
    log_file = tmp_path / "integration.log"
    assert log_file.exists()

    empty_index = build_entity_index([])
    run_state = RunState(
        config=cfg,
        source_path=Path("/source"),
        reference_modules=[],
        source_entities=[],
        source_index=empty_index,
        source_by_id={},
        rules=[],
        compiler_results=[],
        compiler_validations=[],
        run_generated_at=datetime.now(timezone.utc),
        framework_version="test",
    )
    target_state = TargetRunState(
        target_id="t1",
        target_path=Path("/target"),
        target_entities=[],
        target_index=empty_index,
        target_by_id={},
        match_results=[],
        match_by_source={},
        rule_results=[],
        validation_results=[],
    )

    report = build_multi_target_report(run_state, [target_state], cfg)
    assert report["run"]["mode"] == "static-only"
    assert report["run"]["config_snapshot"] is not None
