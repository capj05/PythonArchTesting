"""The reference's architecture model (F4.1): CLI ``--write-model`` and MCP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.cli import main
from pythonarchtesting.mcp_server import authoring
from pythonarchtesting.mcp_server.errors import ToolInputError
from tests.integration.test_architecture_cli import (
    _CASES,
    _RUNTIME,
    _SOLUTION,
    _markers,
    _write,
)


def _model(tmp_path: Path, init: str, *flags: str) -> dict[str, Any]:
    reference = _write(tmp_path / "reference", {"__init__.py": init, **_SOLUTION})
    output = tmp_path / "model.json"
    code = main(["--source", str(reference), "--write-model", str(output), *flags])
    assert code == 0
    return json.loads(output.read_text(encoding="utf-8"))


def test_the_static_model_lists_modules_imports_and_libraries(tmp_path: Path):
    model = _model(tmp_path, _markers('allow=["controller -> models"]'))

    assert model["version"] == 1
    assert {m["name"] for m in model["modules"]} >= {
        "__init__",
        "controller",
        "service",
        "repository",
        "models",
    }
    imports = {item["edge"]: item["at"] for item in model["static"]["imports"]}
    assert imports["service -> models"].startswith("service.py:")
    assert {i["edge"] for i in model["static"]["external"]} == {"repository -> json"}
    declaration = model["declaration"]
    assert declaration["declared"] is True
    assert declaration["allow"] == ["controller -> models"]
    assert "typing" in declaration["ignore_external"]
    assert "runtime" not in model


def test_without_a_declaration_the_defaults_are_described(tmp_path: Path):
    model = _model(tmp_path, "")

    assert model["declaration"]["declared"] is False
    assert model["declaration"]["policy"] == "allow_new_modules"
    assert model["static"]["imports"]


def test_the_full_model_adds_what_the_cases_do(tmp_path: Path):
    model = _model(tmp_path, _markers(_RUNTIME), "--dynamic")

    runtime = model["runtime"]
    assert runtime["status"] == "completed"
    assert "controller -> service" in runtime["calls"]
    assert "service -> repository" in runtime["calls"]
    assert "service -> models.Order" in runtime["instances"]
    assert "repository -> json" in runtime["external"]
    assert model["declaration"]["entry"] == "controller.handle"
    assert model["declaration"]["case_count"] >= 1


def test_the_full_model_says_why_nothing_ran(tmp_path: Path, capsys):
    model = _model(tmp_path, _markers(), "--dynamic")

    assert model["runtime"]["status"] == "not_run"
    assert "entry" in model["runtime"]["reason"]
    assert "did not run" in capsys.readouterr().err


def test_a_broken_declaration_is_reported(tmp_path: Path):
    model = _model(tmp_path, _markers('policy="nonsense"'))

    assert model["declaration"]["problems"]


def test_write_model_takes_no_targets(tmp_path: Path):
    reference = _write(tmp_path / "reference", {"__init__.py": "", **_SOLUTION})
    with pytest.raises(SystemExit):
        main(
            [
                "--source",
                str(reference),
                "--target",
                str(reference),
                "--write-model",
                str(tmp_path / "m.json"),
            ]
        )


def test_mcp_describe_architecture(tmp_path: Path):
    reference = _write(
        tmp_path / "reference", {"__init__.py": _markers(_RUNTIME), **_SOLUTION}
    )

    static = authoring.describe_architecture(str(reference))
    full = authoring.describe_architecture(str(reference), mode="full")

    assert "runtime" not in static
    assert "controller -> service" in full["runtime"]["calls"]
    with pytest.raises(ToolInputError):
        authoring.describe_architecture(str(reference), mode="everything")
    with pytest.raises(ToolInputError):
        authoring.describe_architecture(str(reference), sandbox="limits")
    with pytest.raises(ToolInputError):
        authoring.describe_architecture("relative/path")


def test_a_reference_case_in_error_is_no_completed_run(tmp_path: Path, capsys):
    cases = '[{"args": [{"$new": "service.Missing"}]}]'
    model = _model(
        tmp_path,
        _markers(f'entry="controller.handle", cases={cases}'),
        "--dynamic",
    )

    assert model["runtime"]["status"] == "reference_failed"
    assert "service.Missing" in model["runtime"]["error"]
    assert "did not run" in capsys.readouterr().err


def test_an_invalid_declaration_compares_nothing(tmp_path: Path, capsys):
    model = _model(
        tmp_path,
        _markers(f'entry="controller.nope", cases={_CASES}'),
        "--dynamic",
    )

    declaration = model["declaration"]
    assert declaration["declared"] is True
    assert "policy" not in declaration
    assert any("controller.nope" in p for p in declaration["problems"])
    assert model["compared"] == {"static": "never", "runtime": "never"}
    assert "does not compile" in model["runtime"]["reason"]
    assert "does not compile" in capsys.readouterr().err


def test_what_is_compared_follows_the_declaration(tmp_path: Path):
    assert _model(tmp_path / "a", _markers(_RUNTIME))["compared"] == {
        "static": "always",
        "runtime": "with --dynamic",
    }
    assert _model(tmp_path / "b", "")["compared"] == {
        "static": "with --architecture",
        "runtime": "never",
    }


def test_a_reference_that_is_no_package_is_never_compared(tmp_path: Path):
    reference = _write(tmp_path / "reference", dict(_SOLUTION))
    output = tmp_path / "model.json"
    main(["--source", str(reference), "--write-model", str(output)])

    model = json.loads(output.read_text(encoding="utf-8"))
    assert model["compared"] == {"static": "never", "runtime": "never"}


def test_the_runtime_comparison_also_allows_libraries_only_imported(
    tmp_path: Path,
):
    model = _model(tmp_path, _markers(_RUNTIME), "--dynamic")

    assert "json" in model["runtime"]["libraries_compared"]


def test_mcp_resolves_the_source_path(tmp_path: Path):
    files = {
        "__init__.py": "",
        **_SOLUTION,
        "service.py": _SOLUTION["service.py"].replace(
            "from .models import Order", "from abspkg.models import Order"
        ),
    }
    reference = _write(tmp_path / "abspkg", files)
    (reference / "sub").mkdir()

    model = authoring.describe_architecture(str(reference / "sub" / ".."))

    assert model["package"] == "abspkg"
    assert "service -> models" in {i["edge"] for i in model["static"]["imports"]}


@pytest.mark.parametrize(
    "flags",
    [
        ["--validate-declarations"],
        ["--format", "markdown"],
        ["--output", "x"],
        ["--architecture"],
        ["--project-pattern", "x*"],
    ],
)
def test_write_model_rejects_flags_it_would_ignore(tmp_path: Path, flags):
    reference = _write(tmp_path / "reference", {"__init__.py": "", **_SOLUTION})
    with pytest.raises(SystemExit):
        main(
            ["--source", str(reference), "--write-model", str(tmp_path / "m.json")]
            + flags
        )
