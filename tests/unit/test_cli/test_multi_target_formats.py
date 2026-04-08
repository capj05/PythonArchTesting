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

    monkeypatch.setattr(cli, "load_config", _load_config)
    monkeypatch.setattr(cli, "configure_logging", _configure_logging)
    monkeypatch.setattr(
        cli,
        "resolve_projects_config",
        lambda **kwargs: SimpleNamespace(
            targets=[SimpleNamespace(path=Path("/t1"))]
        ),
    )
    monkeypatch.setattr(cli, "_run_single_target", lambda **kwargs: 0)
    monkeypatch.setattr(cli.os, "getcwd", lambda: "C:/repo")
    monkeypatch.setattr(cli.logging, "warning", _warning)

    exit_code = cli.main(["--target", "a"])

    assert exit_code == 0
    assert captured_kwargs["config_path"] is None
    assert captured_kwargs["discover_from_cwd"] is True
    assert captured_kwargs["cwd"] == "C:/repo"
    assert callable(captured_kwargs["warning_sink"])
    assert events == ["configure_logging", "loader_warning: watch it"]
