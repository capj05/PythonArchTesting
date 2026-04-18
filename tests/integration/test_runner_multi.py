from __future__ import annotations

from pathlib import Path

import pytest

import pythonarchtesting.runner_multi as runner_multi_module
from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.config.projects import resolve_projects_config
from pythonarchtesting.report.api import build_multi_target_report
from pythonarchtesting.runner_multi import run_multi


def _smoke_paths() -> tuple[Path, Path, Path]:
    base = Path(__file__).resolve().parents[1] / "fixtures" / "smoke"
    return (
        base / "source",
        base / "target_ok",
        base / "target_bad",
    )


def _fresh_config():
    return create_config_from_dict({})


def test_run_multi_stable_target_ordering(monkeypatch) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    cfg = _fresh_config()
    source, target_ok, target_bad = _smoke_paths()

    projects = resolve_projects_config(
        cfg,
        source_path=str(source),
        targets=[str(target_bad), str(target_ok)],
    )
    run_state, target_states = run_multi(
        config=cfg,
        projects=projects,
        load_config_first=False,
    )
    report = build_multi_target_report(run_state, target_states, cfg)

    target_ids = [item["target_id"] for item in report["targets"]]
    assert target_ids == sorted(target_ids)
    assert not hasattr(run_state, "arch_rules")


def test_run_multi_target_isolation_and_no_arch_output(monkeypatch) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    cfg = _fresh_config()
    source, target_ok, target_bad = _smoke_paths()

    projects = resolve_projects_config(
        cfg,
        source_path=str(source),
        targets=[str(target_ok), str(target_bad)],
    )
    run_state, target_states = run_multi(
        config=cfg,
        projects=projects,
        load_config_first=False,
    )
    report = build_multi_target_report(run_state, target_states, cfg)
    exit_codes = {item["target_id"]: item["exit_code"] for item in report["targets"]}

    assert exit_codes["target_ok"] == 0
    assert exit_codes["target_bad"] == 1
    assert all(
        not str(item.get("rule_id") or "").startswith(("arch/", "structural/"))
        for target in report["targets"]
        for item in target.get("results") or []
    )


def test_runner_multi_alias_contract_removed() -> None:
    assert not hasattr(runner_multi_module, "runner_multi")

    with pytest.raises(AttributeError):
        _ = runner_multi_module.runner_multi
