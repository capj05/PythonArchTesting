from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import src.cli as cli


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
