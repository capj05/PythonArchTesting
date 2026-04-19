from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.config.projects import TargetSpec
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.evidence.collection import ParsedModule
from pythonarchtesting.run_state import RunState
from pythonarchtesting.runner import evaluate_target, run_projects


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
        "pythonarchtesting.runner.parse_python_modules",
        fake_parse_python_modules,
    )

    target_state = evaluate_target(run_state=run_state, spec=spec)

    assert parse_calls["count"] == 1
    assert target_state.target_id == "target"
    assert not hasattr(run_state, "arch_rules")


def test_run_projects_one_target_returns_one_target_state(tmp_path) -> None:
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

    run_state, target_states = run_projects(
        config=cfg,
        targets=[str(target_dir)],
        source_path=str(source_dir),
        load_config_first=False,
    )

    assert len(target_states) == 1
    assert target_states[0].target_id == target_dir.name


def test_run_projects_one_target_prepares_source_once(monkeypatch, tmp_path) -> None:
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

    run_state, target_states = run_projects(
        config=cfg,
        targets=[str(target_dir)],
        source_path=str(source_dir),
        load_config_first=False,
    )

    # Source should have been prepared — source_entities must be populated
    assert run_state.source_entities
    assert any(
        entity.module_path == "reference" for entity in run_state.source_entities
    )


def test_run_projects_one_target_uses_ordinary_target_id(tmp_path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "my_target"
    source_dir.mkdir()
    target_dir.mkdir()
    (source_dir / "reference.py").write_text(
        "def rule():\n    return 1\n", encoding="utf-8"
    )
    (target_dir / "impl.py").write_text("def rule():\n    return 1\n", encoding="utf-8")

    cfg = create_config_from_dict({"projects": {"source_path": str(source_dir)}})

    run_state, target_states = run_projects(
        config=cfg,
        targets=[str(target_dir)],
        source_path=str(source_dir),
        load_config_first=False,
    )

    assert len(target_states) == 1
    # target_id should be the directory name, not "root" or "__single__"
    assert target_states[0].target_id == target_dir.name
    assert target_states[0].target_id not in ("root", "__single__")
