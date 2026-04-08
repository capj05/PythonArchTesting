from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.config.projects import TargetSpec
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.evidence.collection import ParsedModule
from pythonarchtesting.runner_multi import evaluate_target
from pythonarchtesting.state_multi import RunState


def _run_state(config) -> RunState:
    empty_index = build_entity_index([])
    return RunState(
        config=config,
        source_path=Path("."),
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


def test_evaluate_target_reuses_parsed_modules_for_static_evidence(
    monkeypatch, tmp_path
) -> None:
    config = create_config_from_dict({})
    run_state = _run_state(config)
    spec = TargetSpec(target_id="target", path=tmp_path)
    parsed = ParsedModule(
        file_path=tmp_path / "sample.py",
        file_text="def f():\n    return 1\n",
        tree=ast.parse("def f():\n    return 1\n"),
        module_path="sample",
        filepath_rel="sample.py",
    )
    parse_calls = {"count": 0}

    def fake_parse_python_modules(*, root_path, config, target_module_name):
        parse_calls["count"] += 1
        return [parsed], []

    monkeypatch.setattr(
        "pythonarchtesting.runner_multi.parse_python_modules",
        fake_parse_python_modules,
    )

    target_state = evaluate_target(run_state=run_state, spec=spec)

    assert parse_calls["count"] == 1
    assert target_state.target_id == "target"
    assert not hasattr(run_state, "arch_rules")
