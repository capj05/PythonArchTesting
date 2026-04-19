import json
from pathlib import Path

import pytest

from pythonarchtesting.cli import main


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


def _write_logical_view_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "source"
    target = base / "target"
    source.mkdir()
    target.mkdir()

    (source / "views.py").write_text(
        """
from typing import Annotated

from web import render
from pythonarchtesting.rules import required_entity_signature


def show_page(request):
    __archtest__: Annotated[None, required_entity_signature(mode="exact")]
    return render(request, "pages/home.html", {"title": "Home"})
""".strip() + "\n",
        encoding="utf-8",
    )
    (source / "helpers.py").write_text(
        """
from typing import Annotated

from pythonarchtesting.rules import required_entity_signature


def compute_total(values):
    __archtest__: Annotated[None, required_entity_signature(mode="exact")]
    return sum(values)
""".strip() + "\n",
        encoding="utf-8",
    )
    (target / "views.py").write_text(
        """
from web import render


def show_page(request):
    return render(request, "pages/home.html", {"title": "Home"})
""".strip() + "\n",
        encoding="utf-8",
    )
    return source, target


def test_run_smoke_json(capsys, monkeypatch, tmp_path):
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


def test_annotation_style_smoke_source_emits_required_signature_rule_ids(
    capsys, monkeypatch, tmp_path
):
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

    rule_ids = {
        str(item.get("rule_id") or "")
        for target in data.get("targets") or []
        for item in target.get("results") or []
    }

    assert exit_code == 1
    assert {
        "API001/required_entity_signature/v1",
        "API001/required_entity_signature_return/v1",
    }.issubset(rule_ids)


def test_run_cli_rejects_removed_runtime_overrides(monkeypatch, tmp_path):
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


def test_run_cli_rejects_removed_runtime_isolation(monkeypatch, tmp_path):
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


def test_run_cli_rejects_removed_allow_unsafe_flag(monkeypatch, tmp_path):
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


def test_run_rejects_non_text_json_format(monkeypatch, tmp_path):
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


def test_one_target_cli_produces_run_report_json(capsys, monkeypatch, tmp_path):
    config_path = _write_smoke_config(tmp_path)
    source, target_ok, _ = _smoke_paths()
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--target",
            str(target_ok),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    data = _parse_json_output(captured.out)

    assert exit_code in (0, 1)
    assert "targets" in data
    assert "summary" in data
    assert data["summary"]["targets_total"] == 1


def test_validation_scope_logical_views_filters_non_template_functions(
    monkeypatch, capsys, tmp_path
):
    config_path = _write_smoke_config(tmp_path)
    source, target = _write_logical_view_fixture(tmp_path)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    exit_code_all = main(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--target",
            str(target),
            "--format",
            "json",
        ]
    )
    captured_all = capsys.readouterr()
    data_all = _parse_json_output(captured_all.out)

    exit_code_scoped = main(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--target",
            str(target),
            "--format",
            "json",
            "--validation-scope",
            "logical-views",
        ]
    )
    captured_scoped = capsys.readouterr()
    data_scoped = _parse_json_output(captured_scoped.out)

    assert exit_code_all == 1
    assert data_all["summary"]["targets_failed"] == 1
    assert exit_code_scoped == 0
    assert data_scoped["summary"]["targets_failed"] == 0
