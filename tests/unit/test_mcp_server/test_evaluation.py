from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.dynamic import sandbox as sandbox_module
from pythonarchtesting.dynamic.sandbox import SandboxUnavailableError
from pythonarchtesting.mcp_server import evaluation
from pythonarchtesting.mcp_server.errors import ToolInputError
from pythonarchtesting.mcp_server.evaluation import (
    run_evaluation,
    validate_declarations_tool,
)

MUTANTS_DIR = Path(__file__).parents[3] / "example" / "architectural_mutants"
REFERENCE = str((MUTANTS_DIR / "reference").resolve())
SOLUTION = str((MUTANTS_DIR / "solution").resolve())


def test_static_run_writes_both_reports(tmp_path: Path) -> None:
    result = run_evaluation(REFERENCE, str(tmp_path / "out"), targets=[SOLUTION])
    run_dir = Path(result["run_dir"])
    assert (run_dir / "report.json").is_file()
    assert (run_dir / "markdown").is_dir()
    assert result["report_json"] == str(run_dir / "report.json")
    assert result["report_markdown"] == str(run_dir / "markdown")
    assert result["exit_code"] == 0
    assert result["runtime_rules_skipped"] == 10
    assert result["runtime_results_unverified"] == 0
    assert result["mode"] == "static-only"
    assert result["config"] == "defaults"


def test_two_runs_get_distinct_dirs(tmp_path: Path) -> None:
    out = str(tmp_path / "out")
    first = run_evaluation(REFERENCE, out, targets=[SOLUTION])
    second = run_evaluation(REFERENCE, out, targets=[SOLUTION])
    assert first["run_dir"] != second["run_dir"]
    assert Path(first["run_dir"]).is_dir()
    assert Path(second["run_dir"]).is_dir()


def test_progress_called_per_target(tmp_path: Path) -> None:
    calls: list[tuple[int, int, str]] = []
    run_evaluation(
        REFERENCE,
        str(tmp_path),
        targets=[SOLUTION, REFERENCE],
        on_progress=lambda i, n, t: calls.append((i, n, t)),
    )
    assert [(i, n) for i, n, _ in calls] == [(1, 2), (2, 2)]


def test_relative_source_rejected(tmp_path: Path) -> None:
    with pytest.raises(ToolInputError, match="absolute"):
        run_evaluation("reference", str(tmp_path), targets=[SOLUTION])


def test_targets_and_targets_dir_exclusive(tmp_path: Path) -> None:
    with pytest.raises(ToolInputError, match="exactly one"):
        run_evaluation(
            REFERENCE, str(tmp_path), targets=[SOLUTION], targets_dir=str(tmp_path)
        )
    with pytest.raises(ToolInputError, match="exactly one"):
        run_evaluation(REFERENCE, str(tmp_path))


def test_pattern_requires_targets_dir(tmp_path: Path) -> None:
    with pytest.raises(ToolInputError, match="targets_dir"):
        run_evaluation(
            REFERENCE, str(tmp_path), targets=[SOLUTION], project_pattern="*"
        )


def test_sandbox_without_dynamic_rejected(tmp_path: Path) -> None:
    with pytest.raises(ToolInputError, match="dynamic"):
        run_evaluation(REFERENCE, str(tmp_path), targets=[SOLUTION], sandbox="limits")


def test_sandbox_none_rejected(tmp_path: Path) -> None:
    with pytest.raises(ToolInputError, match="unconfined"):
        run_evaluation(
            REFERENCE, str(tmp_path), targets=[SOLUTION], dynamic=True, sandbox="none"
        )


def test_dynamic_defaults_to_bwrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Any] = []

    def fake_check(policy: Any) -> None:
        seen.append(policy)
        raise SandboxUnavailableError("bwrap is not installed")

    monkeypatch.setattr(sandbox_module, "check_available", fake_check)
    with pytest.raises(ToolInputError, match="not available"):
        run_evaluation(REFERENCE, str(tmp_path), targets=[SOLUTION], dynamic=True)
    assert seen[0].mode == "bwrap"


def test_config_found_next_to_source(tmp_path: Path) -> None:
    course = tmp_path / "course"
    shutil.copytree(REFERENCE, course / "reference")
    (course / ".pythonarchtesting").write_text("")
    result = run_evaluation(
        str(course / "reference"),
        str(tmp_path / "out"),
        targets=[SOLUTION],
    )
    assert result["config"].endswith("course/.pythonarchtesting")


def test_explicit_config_must_exist(tmp_path: Path) -> None:
    with pytest.raises(ToolInputError, match="config"):
        evaluation.resolve_config(Path(REFERENCE), str(tmp_path / "missing"))


def test_validate_declarations_tool_reports_config() -> None:
    result = validate_declarations_tool(REFERENCE)
    assert result["config"] == "defaults"
    assert result["exit_code"] == 0


def test_validate_declarations_bad_scope_rejected() -> None:
    with pytest.raises(ToolInputError, match="validation_scope"):
        validate_declarations_tool(REFERENCE, validation_scope="bogus")


def test_run_evaluation_bad_scope_rejected_before_any_write(tmp_path: Path) -> None:
    out = tmp_path / "out"
    with pytest.raises(ToolInputError, match="validation_scope"):
        run_evaluation(REFERENCE, str(out), targets=[SOLUTION], validation_scope="x")
    assert not out.exists()
