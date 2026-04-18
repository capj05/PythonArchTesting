from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import pythonarchtesting.cli as cli


def _stub_config():
    return SimpleNamespace(
        projects=SimpleNamespace(targets=[], targets_dir=None, target_path=None),
    )


def _stub_projects_cfg():
    return SimpleNamespace(
        source_path=Path("/source"),
        targets=[
            SimpleNamespace(path=Path("/t1")),
            SimpleNamespace(path=Path("/t2")),
        ],
    )


def _stub_run_multi_result():
    from pythonarchtesting.entities import build_entity_index
    from pythonarchtesting.state_multi import RunState, TargetRunState
    from datetime import datetime, timezone

    empty_index = build_entity_index([])
    from pythonarchtesting.config.data import create_config_from_dict
    cfg = create_config_from_dict({})
    run_state = RunState(
        config=cfg,
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
    target_state = TargetRunState(
        target_id="t1",
        target_path=Path("/t1"),
        target_entities=[],
        target_index=empty_index,
        target_by_id={},
        match_results=[],
        match_by_source={},
        rule_results=[],
        validation_results=[],
        exit_code=0,
    )
    return run_state, [target_state]


def test_cli_multi_target_markdown_requires_output(monkeypatch):
    monkeypatch.setattr(cli, "load_config", lambda **kwargs: _stub_config())
    monkeypatch.setattr(cli, "configure_logging", lambda config: None)
    monkeypatch.setattr(
        cli, "resolve_projects_config", lambda **kwargs: _stub_projects_cfg()
    )

    with pytest.raises(SystemExit):
        cli.main(
            [
                "--source",
                "src",
                "--target",
                "a",
                "--target",
                "b",
                "--format",
                "markdown",
            ]
        )


def test_cli_multi_target_rejects_removed_html_format(monkeypatch):
    monkeypatch.setattr(cli, "load_config", lambda **kwargs: _stub_config())
    monkeypatch.setattr(cli, "configure_logging", lambda config: None)
    monkeypatch.setattr(
        cli, "resolve_projects_config", lambda **kwargs: _stub_projects_cfg()
    )

    with pytest.raises(SystemExit):
        cli.main(
            [
                "--source",
                "src",
                "--target",
                "a",
                "--target",
                "b",
                "--format",
                "html",
            ]
        )


def test_cli_main_explicitly_enables_cwd_discovery_and_logs_buffered_warnings(
    monkeypatch,
):
    captured_kwargs = {}
    events = []

    def _load_config(**kwargs):
        captured_kwargs.update(kwargs)
        kwargs["warning_sink"](
            SimpleNamespace(code="loader_warning", message="watch it")
        )
        return _stub_config()

    def _configure_logging(config):
        events.append("configure_logging")

    def _warning(message, *args, **kwargs):
        assert events == ["configure_logging"]
        events.append(message % args)

    def _run_multi(*args, **kwargs):
        return _stub_run_multi_result()

    def _generate_report(run_state, target_states, fmt, config, output):
        return "{}"

    def _get_exit_code(run_state, target_states, config):
        return 0

    monkeypatch.setattr(cli, "load_config", _load_config)
    monkeypatch.setattr(cli, "configure_logging", _configure_logging)
    monkeypatch.setattr(
        cli,
        "resolve_projects_config",
        lambda **kwargs: SimpleNamespace(targets=[SimpleNamespace(path=Path("/t1"))]),
    )
    monkeypatch.setattr(cli, "run_multi", _run_multi)
    monkeypatch.setattr(cli, "generate_multi_target_report", _generate_report)
    monkeypatch.setattr(cli, "get_multi_exit_code", _get_exit_code)
    monkeypatch.setattr(cli.os, "getcwd", lambda: "C:/repo")
    monkeypatch.setattr(cli.logging, "warning", _warning)

    exit_code = cli.main(["--target", "a"])

    assert exit_code == 0
    assert captured_kwargs["config_path"] is None
    assert captured_kwargs["discover_from_cwd"] is True
    assert captured_kwargs["cwd"] == "C:/repo"
    assert callable(captured_kwargs["warning_sink"])
    assert events == ["configure_logging", "loader_warning: watch it"]


def test_cli_main_autoloads_dotfile_config_without_explicit_config(
    tmp_path, monkeypatch
):
    (tmp_path / ".pythonarchtesting").write_text(
        "[performance]\ndefault_timeout = 45\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "configure_logging", lambda config: None)
    monkeypatch.setattr(
        cli,
        "resolve_projects_config",
        lambda **kwargs: SimpleNamespace(
            source_path=Path("/source"),
            targets=[SimpleNamespace(path=Path("/t1"))],
        ),
    )

    seen = {}

    def _run_multi(*args, **kwargs):
        seen["timeout"] = kwargs["config"].performance.default_timeout
        return _stub_run_multi_result()

    def _generate_report(run_state, target_states, fmt, config, output):
        return "{}"

    def _get_exit_code(run_state, target_states, config):
        return 0

    monkeypatch.setattr(cli, "run_multi", _run_multi)
    monkeypatch.setattr(cli, "generate_multi_target_report", _generate_report)
    monkeypatch.setattr(cli, "get_multi_exit_code", _get_exit_code)

    exit_code = cli.main(["--target", "a"])

    assert exit_code == 0
    assert seen["timeout"] == 45


def test_cli_single_target_markdown_requires_output(monkeypatch):
    monkeypatch.setattr(cli, "load_config", lambda **kwargs: _stub_config())
    monkeypatch.setattr(cli, "configure_logging", lambda config: None)
    monkeypatch.setattr(
        cli,
        "resolve_projects_config",
        lambda **kwargs: SimpleNamespace(
            source_path=Path("/source"),
            targets=[SimpleNamespace(path=Path("/t1"))],
        ),
    )

    with pytest.raises(SystemExit):
        cli.main(
            [
                "--source",
                "src",
                "--target",
                "a",
                "--format",
                "markdown",
            ]
        )
