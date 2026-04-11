from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.config.projects import TargetSpec
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.evidence.collection import ParsedModule
from pythonarchtesting.runner_multi import evaluate_target
from pythonarchtesting.runner_multi.orchestrator import (
    run_single_target as run_single_target_unified,
)
from pythonarchtesting.state import ProjectState
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


def test_run_single_target_returns_run_state_and_target_state_without_project_state(
    monkeypatch, tmp_path
) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    (source_dir / "reference.py").write_text(
        "def rule():\n    return 1\n", encoding="utf-8"
    )
    (target_dir / "target.py").write_text(
        "def implementation():\n    return 1\n", encoding="utf-8"
    )

    cfg = create_config_from_dict({"projects": {"source_path": str(source_dir)}})

    def boom_init(self, *args, **kwargs):
        raise AssertionError("ProjectState singleton constructor should not be used")

    monkeypatch.setattr(ProjectState, "__init__", boom_init)

    run_state, target_state = run_single_target_unified(
        config=cfg,
        target_path=str(target_dir),
        reference_modules=[],
    )

    assert run_state.source_path == source_dir.resolve()
    assert run_state.source_entities
    assert any(
        entity.module_path == "reference" for entity in run_state.source_entities
    )
    assert target_state.target_id == target_dir.name
    assert target_state.target_entities
    assert not hasattr(run_state, "arch_rules")


def test_run_single_target_discovers_source_when_reference_modules_absent(
    tmp_path,
) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    (source_dir / "reference.py").write_text(
        "def rule():\n    return 1\n", encoding="utf-8"
    )
    (target_dir / "target.py").write_text(
        "def implementation():\n    return 1\n", encoding="utf-8"
    )

    cfg = create_config_from_dict({"projects": {"source_path": str(source_dir)}})

    run_state, target_state = run_single_target_unified(
        config=cfg,
        target_path=str(target_dir),
        reference_modules=[],
    )

    assert run_state.source_entities
    assert run_state.source_by_id
    assert run_state.reference_modules == []
    assert target_state.target_entities


def test_run_single_target_resolves_reference_modules_from_configured_source_root(
    tmp_path,
) -> None:
    source_dir = tmp_path / "reference"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    (source_dir / "calculator.pyi").write_text(
        "from typing import Annotated\n\n"
        "def add(a: int, b: int) -> "
        'Annotated[int, ("required_entity_signature", {"mode": "exact"})]: ...\n',
        encoding="utf-8",
    )
    (target_dir / "calculator.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )

    cfg = create_config_from_dict(
        {
            "discovery": {"included_file_patterns": ["*.pyi"]},
            "projects": {"source_path": str(source_dir)},
        }
    )

    run_state, target_state = run_single_target_unified(
        config=cfg,
        target_path=str(target_dir),
        reference_modules=["calculator"],
    )

    assert run_state.source_path == source_dir.resolve()
    assert run_state.reference_modules == ["calculator"]
    assert any(
        entity.module_path == "calculator" for entity in run_state.source_entities
    )
    assert target_state.target_entities
