from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.report.json_generator import JSONReportGenerator
from pythonarchtesting.run_state import RunState, TargetRunState


def _cfg():
    return create_config_from_dict({"report": {}})


def _run_state() -> RunState:
    cfg = _cfg()
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


def _target_state() -> TargetRunState:
    empty_index = build_entity_index([])
    return TargetRunState(
        target_id="target-a",
        target_path=Path("/targets/target-a"),
        target_entities=[],
        target_index=empty_index,
        target_by_id={},
        match_results=[],
        match_by_source={},
        rule_results=[],
        validation_results=[],
    )


def test_json_report_generator_accepts_run_state_tuple():
    generator = JSONReportGenerator((_run_state(), [_target_state()]))

    rendered = generator.generate()
    report = json.loads(rendered)

    assert report["schema_version"] == "2"
    assert [target["target_id"] for target in report["targets"]] == ["target-a"]
