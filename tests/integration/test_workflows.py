import json
from pathlib import Path

import pytest

import src.cli as cli_module
from src.cli import main


def _smoke_paths() -> tuple[Path, Path, Path]:
    base = Path(__file__).resolve().parents[1] / "fixtures" / "smoke"
    return (
        base / "source",
        base / "target_ok",
        base / "target_bad",
    )


def _parse_json_output(output: str) -> dict:
    payload = output.strip()
    start = payload.find("{")
    if start > 0:
        payload = payload[start:]
    return json.loads(payload)


def _write_smoke_config(path: Path) -> Path:
    config_path = path / "smoke_cli.conf"
    config_path.write_text(
        """
[report]
include_config_snapshot = true
""".strip() + "\n",
        encoding="utf-8",
    )
    return config_path


def test_multi_target_smoke_json(capsys, monkeypatch, tmp_path):
    config_path = _write_smoke_config(tmp_path)

    source, target_ok, target_bad = _smoke_paths()
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    exit_code = main(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--target",
            str(target_ok),
            "--target",
            str(target_bad),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    data = _parse_json_output(captured.out)

    assert exit_code == 1
    assert data["schema_version"] == "2"
    assert data["summary"]["targets_total"] == 2
    assert data["summary"]["targets_failed"] == 1
    assert data["exit_code"] == 1
    assert data["run"]["mode"] == "static-only"
    assert data["run"]["config_snapshot"] is not None
    assert (
        str(data["run"]["config_snapshot"]["report"]["include_config_snapshot"]).lower()
        == "true"
    )


def test_multi_target_cli_rejects_removed_runtime_overrides(monkeypatch, tmp_path):
    config_path = _write_smoke_config(tmp_path)

    source, target_ok, target_bad = _smoke_paths()
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    with pytest.raises(SystemExit):
        main(
            [
                "--config",
                str(config_path),
                "--source",
                str(source),
                "--target",
                str(target_ok),
                "--target",
                str(target_bad),
                "--format",
                "json",
                "--runtime-max-probe-modules",
                "7",
                "--runtime-fast",
            ]
        )


def test_multi_target_cli_rejects_removed_runtime_isolation(monkeypatch, tmp_path):
    config_path = _write_smoke_config(tmp_path)
    source, target_ok, target_bad = _smoke_paths()
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    with pytest.raises(SystemExit):
        main(
            [
                "--config",
                str(config_path),
                "--source",
                str(source),
                "--target",
                str(target_ok),
                "--target",
                str(target_bad),
                "--format",
                "json",
                "--runtime-isolation",
                "unsafe",
            ]
        )


def test_multi_target_cli_rejects_removed_allow_unsafe_flag(monkeypatch, tmp_path):
    config_path = _write_smoke_config(tmp_path)
    source, target_ok, target_bad = _smoke_paths()
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    with pytest.raises(SystemExit):
        main(
            [
                "--config",
                str(config_path),
                "--source",
                str(source),
                "--target",
                str(target_ok),
                "--target",
                str(target_bad),
                "--format",
                "json",
                "--allow-unsafe-probes",
            ]
        )


def test_multi_target_rejects_non_text_json_format(monkeypatch, tmp_path):
    config_path = _write_smoke_config(tmp_path)
    source, target_ok, target_bad = _smoke_paths()
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    with pytest.raises(SystemExit):
        main(
            [
                "--config",
                str(config_path),
                "--source",
                str(source),
                "--target",
                str(target_ok),
                "--target",
                str(target_bad),
                "--format",
                "html",
            ]
        )


def test_multi_target_cli_does_not_use_project_state_singleton(monkeypatch, tmp_path):
    config_path = _write_smoke_config(tmp_path)
    source, target_ok, target_bad = _smoke_paths()
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    monkeypatch.setattr(
        cli_module,
        "ProjectState",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("ProjectState should not be used for multi-target CLI")
        ),
    )
    exit_code = main(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--target",
            str(target_ok),
            "--target",
            str(target_bad),
            "--format",
            "json",
        ]
    )

    assert exit_code == 1


def test_single_target_cli_does_not_use_project_state_singleton_constructor(
    monkeypatch, tmp_path
):
    config_path = _write_smoke_config(tmp_path)
    _, target_ok, _ = _smoke_paths()
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    original_factory = cli_module.ProjectState
    calls = {"count": 0}

    def _counting_factory(*args, **kwargs):
        calls["count"] += 1
        return original_factory(*args, **kwargs)

    monkeypatch.setattr(cli_module, "ProjectState", _counting_factory)
    exit_code = main(
        [
            "--config",
            str(config_path),
            "--target",
            str(target_ok),
            "--format",
            "json",
        ]
    )

    assert calls["count"] == 1
    assert exit_code in (0, 1)
