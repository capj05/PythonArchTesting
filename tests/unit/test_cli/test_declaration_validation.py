from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

import pythonarchtesting.cli as cli
from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.declaration_validation import collect_declaration_diagnostics
from pythonarchtesting.runner_multi.source_prep import prepare_source


def _write_source_file(root: Path, body: str, filename: str = "rules.py") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / filename
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    return path


def _config() -> object:
    return create_config_from_dict({})


def test_collect_declaration_diagnostics_covers_warning_and_invalid_cases(tmp_path):
    source_dir = tmp_path / "source"
    _write_source_file(
        source_dir,
        """
        from typing import Annotated
        from pythonarchtesting.rules import forbid_imports, required_method

        __archtest__: Annotated[None, required_method(signature_mode="exact")] = None

        def invalid_container() -> None:
            __archtest__: list[int]

        def invalid_metadata() -> None:
            __archtest__: Annotated[None, ("required_method", ["exact"])]

        def invalid_surface(
            value: Annotated[int, forbid_imports("requests", scope="entity")],
        ) -> int:
            return value
        """,
    )

    run_state = prepare_source(config=_config(), source_path=source_dir)
    diagnostics = collect_declaration_diagnostics(run_state)
    issue_kinds = {
        issue["kind"] for item in diagnostics for issue in item.get("issues") or []
    }
    categories = {item["category"] for item in diagnostics}

    assert "assigned_value" in issue_kinds
    assert {"container", "metadata", "surface"}.issubset(issue_kinds)
    assert "invalid_declaration" in categories
    assert "declaration_warning" in categories


def test_collect_declaration_diagnostics_covers_unknown_metadata(tmp_path):
    source_dir = tmp_path / "source"
    _write_source_file(
        source_dir,
        """
        from typing import Annotated

        def invalid_unknown() -> None:
            __archtest__: Annotated[None, ("custom_rule", {"enabled": True})]
        """,
    )

    run_state = prepare_source(config=_config(), source_path=source_dir)
    diagnostics = collect_declaration_diagnostics(run_state)

    assert any(
        issue["kind"] == "unknown_metadata"
        for item in diagnostics
        for issue in item.get("issues") or []
    )


def test_collect_declaration_diagnostics_includes_invalid_import_policy_mode(
    tmp_path,
):
    source_dir = tmp_path / "source"
    _write_source_file(
        source_dir,
        """
        from typing import Annotated

        def invalid_mode_rule() -> None:
            __archtest__: Annotated[
                None,
                ("forbid_imports", {"forbidden": ["requests"], "mode": "invalid"}),
            ]
        """,
    )

    run_state = prepare_source(config=_config(), source_path=source_dir)
    diagnostics = collect_declaration_diagnostics(run_state)

    assert any(
        item["check_type"] == "compiler_invalid_import_policy_mode"
        and item["category"] == "invalid_declaration"
        and item["severity"] == "error"
        for item in diagnostics
    )


def test_cli_validate_declarations_returns_zero_for_warning_only_json(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.chdir(Path(__file__).resolve().parents[3])
    source_dir = tmp_path / "source"
    _write_source_file(
        source_dir,
        """
        from typing import Annotated
        from pythonarchtesting.rules import required_method

        __archtest__: Annotated[None, required_method(signature_mode="exact")] = None
        """,
    )

    exit_code = cli.main(
        [
            "--validate-declarations",
            "--source",
            str(source_dir),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["summary"]["warning_declarations"] == 1
    assert any(
        item["check_type"] == "annotation_declaration_warning"
        for item in payload["diagnostics"]
    )


def test_cli_validate_declarations_returns_non_zero_for_invalid_declaration(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.chdir(Path(__file__).resolve().parents[3])
    source_dir = tmp_path / "source"
    _write_source_file(
        source_dir,
        """
        from typing import Annotated

        def invalid_rule() -> None:
            __archtest__: Annotated[None, ("required_method", ["exact"])]
        """,
    )

    exit_code = cli.main(
        [
            "--validate-declarations",
            "--source",
            str(source_dir),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["summary"]["invalid_declarations"] == 1
    assert payload["summary"]["errors_total"] == 1
    assert payload["diagnostics"][0]["issues"][0]["kind"] == "metadata"


def test_cli_validate_declarations_reports_source_syntax_error(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.chdir(Path(__file__).resolve().parents[3])
    source_dir = tmp_path / "source"
    _write_source_file(source_dir, "def broken(:\n    pass\n")

    exit_code = cli.main(
        [
            "--validate-declarations",
            "--source",
            str(source_dir),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["summary"]["syntax_errors"] == 1
    assert payload["diagnostics"][0]["check_type"] == "extraction/syntax_error"


def test_cli_validate_declarations_reports_invalid_import_policy_mode(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.chdir(Path(__file__).resolve().parents[3])
    source_dir = tmp_path / "source"
    _write_source_file(
        source_dir,
        """
        from typing import Annotated

        def invalid_mode_rule() -> None:
            __archtest__: Annotated[
                None,
                ("forbid_imports", {"forbidden": ["requests"], "mode": "invalid"}),
            ]
        """,
    )

    exit_code = cli.main(
        [
            "--validate-declarations",
            "--source",
            str(source_dir),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["summary"]["invalid_declarations"] == 1
    assert payload["summary"]["errors_total"] == 1
    assert (
        payload["diagnostics"][0]["check_type"] == "compiler_invalid_import_policy_mode"
    )


def test_cli_validate_declarations_writes_output_file(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[3])
    source_dir = tmp_path / "source"
    output_path = tmp_path / "declarations.json"
    _write_source_file(
        source_dir,
        """
        from typing import Annotated

        def invalid_rule() -> None:
            __archtest__: list[int]
        """,
    )

    exit_code = cli.main(
        [
            "--validate-declarations",
            "--source",
            str(source_dir),
            "--format",
            "json",
            "--output",
            str(output_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert "Report written to" in captured.out
    assert payload["summary"]["invalid_declarations"] == 1


def test_prepare_source_discovers_stub_only_reference_tree(tmp_path):
    source_dir = tmp_path / "reference"
    package_dir = source_dir / "pkg"
    package_dir.mkdir(parents=True)
    _write_source_file(
        package_dir,
        """
        from typing import Annotated

        __archtest__: Annotated[
            None,
            ("forbid_imports", {"forbidden": ["statistics"], "scope": "package"}),
        ]
        """,
        filename="__init__.pyi",
    )
    config = create_config_from_dict(
        {
            "discovery": {"included_file_patterns": ["*.pyi"]},
            "projects": {"source_path": str(source_dir)},
        }
    )

    run_state = prepare_source(config=config, source_path=source_dir)

    assert run_state.source_entities
    assert any(
        entity.filepath_rel.endswith("__init__.pyi")
        for entity in run_state.source_entities
    )


def test_cli_validate_declarations_supports_stub_only_reference_project(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.chdir(Path(__file__).resolve().parents[3])
    source_dir = tmp_path / "reference"
    package_dir = source_dir / "pkg"
    package_dir.mkdir(parents=True)
    _write_source_file(
        package_dir,
        """
        from typing import Annotated

        __archtest__: Annotated[
            None,
            ("forbid_imports", {"forbidden": ["statistics"], "scope": "package"}),
        ]
        """,
        filename="__init__.pyi",
    )
    config_path = tmp_path / "stub.conf"
    config_path.write_text(
        "[discovery]\nincluded_file_patterns = *.pyi\n",
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "--config",
            str(config_path),
            "--validate-declarations",
            "--source",
            str(source_dir),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["summary"]["source_entities"] > 0
    assert payload["summary"]["files_scanned"] == 1


def test_cli_validate_declarations_stub_only_reference_modules_require_pyi(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.chdir(Path(__file__).resolve().parents[3])
    source_dir = tmp_path / "reference"
    _write_source_file(
        source_dir,
        """
        from typing import Annotated

        __archtest__: Annotated[None, ("required_method", {"signature_mode": "exact"})]
        """,
        filename="rules.py",
    )
    config_path = tmp_path / "stub.conf"
    config_path.write_text(
        "[discovery]\nincluded_file_patterns = *.pyi\n",
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "--config",
            str(config_path),
            "--validate-declarations",
            "--source",
            str(source_dir),
            "--reference-modules",
            "rules",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["summary"]["source_entities"] == 0
    assert payload["summary"]["source_resolution_errors"] == 1
    assert payload["diagnostics"][0]["check_type"] == "extraction/source_resolution"


def test_cli_validate_declarations_rejects_target_flags(tmp_path):
    source_dir = tmp_path / "source"
    _write_source_file(source_dir, "def ok() -> None:\n    return None\n")

    with pytest.raises(SystemExit):
        cli.main(
            [
                "--validate-declarations",
                "--source",
                str(source_dir),
                "--target",
                str(tmp_path / "target"),
            ]
        )


def test_cli_validate_declarations_rejects_unsupported_format(tmp_path):
    source_dir = tmp_path / "source"
    _write_source_file(source_dir, "def ok() -> None:\n    return None\n")

    with pytest.raises(SystemExit):
        cli.main(
            [
                "--validate-declarations",
                "--source",
                str(source_dir),
                "--format",
                "html",
            ]
        )


def test_cli_validate_declarations_rejects_markdown_format(tmp_path):
    source_dir = tmp_path / "source"
    _write_source_file(source_dir, "def ok() -> None:\n    return None\n")

    with pytest.raises(SystemExit):
        cli.main(
            [
                "--validate-declarations",
                "--source",
                str(source_dir),
                "--format",
                "markdown",
            ]
        )
