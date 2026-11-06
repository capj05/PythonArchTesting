"""M3: a task (``task.toml`` beside an unannotated reference) prepared and used.

``prepare_task`` on both example tasks accepts them, with the coverage of
every typical error; a role the catalogue needs and the task leaves unbound
fails clearly (Review Focus 5); and ``run_evaluation`` takes the task
directory as its source, records its principle and judges the class by it.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import anyio
import pytest

from pythonarchtesting.mcp_server.reports import class_overview
from pythonarchtesting.mcp_server.tasks import prepare_task

_EXAMPLES = Path(__file__).resolve().parents[2] / "example" / "principles"
_COVERAGE = {
    "io_separation": {
        "print_instead_of_return": "killed",
        "input_in_logic": "killed",
        "output_through_helper": "not_verifiable_by_mutation",
        "file_io_in_logic": "killed",
        "logic_in_main": "not_verifiable_by_mutation",
    },
    "encapsulation": {
        "bypass_method": "not_verifiable_by_mutation",
        "mutate_container": "not_verifiable_by_mutation",
        "replace_attribute": "killed",
        "read_private": "gap",
    },
}


def _files(root: Path) -> dict[Path, bytes]:
    return {
        path: path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


@pytest.mark.parametrize("principle", sorted(_COVERAGE))
def test_prepare_task_accepts_the_example_task(principle: str) -> None:
    task = _EXAMPLES / principle
    before = _files(task / "reference")
    before[task / "task.toml"] = (task / "task.toml").read_bytes()

    result = prepare_task(str(task), sandbox="limits")

    assert result["accepted"] is True, result
    assert result["principle"] == principle
    assert result["problems"] == []
    assert result["reference_passes"] is True
    assert result["checks"]
    for check in result["checks"]:
        assert check["cases_ran"] is True, check
        assert check["coverage"] >= 0.8, check
    assert {e["error"]: e["status"] for e in result["errors"]} == _COVERAGE[principle]
    for entry in result["errors"]:
        if entry["status"] == "killed":
            # Every mutant caught, at least one as this very error (its
            # signature matched): replace_attribute's mutants write the
            # private _stock, not a method attribute.
            assert entry["killed"] + entry["killed_other"] == entry["mutants"]
            assert entry["killed"] > 0 and entry["signature_matched"] is True, entry
    # Nothing is written into the task.
    after = _files(task / "reference")
    after[task / "task.toml"] = (task / "task.toml").read_bytes()
    assert after == before


def test_prepare_task_names_a_role_the_task_leaves_unbound(tmp_path: Path) -> None:
    task = tmp_path / "encapsulation"
    shutil.copytree(
        _EXAMPLES / "encapsulation", task, ignore=shutil.ignore_patterns("assignments")
    )
    toml = task / "task.toml"
    text = toml.read_text(encoding="utf-8")
    toml.write_text(text.replace('client = ["shop"]\n', ""), encoding="utf-8")

    result = prepare_task(str(task), sandbox="limits")

    assert result["accepted"] is False
    assert result["checks"] == [] and result["errors"] == []
    assert any("role 'client' is not bound" in p for p in result["problems"])


class _Context:
    async def report_progress(self, *args: Any) -> None:
        return None


def test_run_evaluation_takes_the_task_as_its_source(tmp_path: Path) -> None:
    pytest.importorskip("mcp")
    from mcp.server.mcpserver.exceptions import ToolError

    from pythonarchtesting.mcp_server import server

    task = _EXAMPLES / "encapsulation"
    submissions = tmp_path / "submissions"
    for variant, student in (
        ("ok_basic", "xxxx01_novak"),
        ("err_sell_bypasses_remove", "xxxx02_dvorak"),
    ):
        shutil.copytree(task / "assignments" / variant, submissions / student)

    async def call(output_dir: Path, **extra: Any) -> dict[str, Any]:
        return await server.run_evaluation(
            _Context(),  # type: ignore[arg-type]
            source=str(task),
            output_dir=str(output_dir),
            targets_dir=str(submissions),
            sandbox="limits",
            **extra,
        )

    result = anyio.run(call, tmp_path / "out")

    # The task implies its principle: the run is dynamic and records it.
    assert result["principle"] == "encapsulation"
    assert result["dynamic_forced"] is True
    overview = class_overview(result["report_json"])
    assert overview["principle"] == "encapsulation"
    assert (overview["passed"], overview["failed"]) == (1, 1)
    assert list(overview["by_error"]) == ["bypass_method"]
    with pytest.raises(ToolError, match="not the task's principle"):

        async def other() -> dict[str, Any]:
            return await call(tmp_path / "other", principle="io_separation")

        anyio.run(other)


def test_prepare_task_names_a_compiler_warning_among_its_problems(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A declaration the compiler refuses with a warning (compiler_invalid_param)
    keeps the task from being accepted, and says why. ``bind_task`` refuses
    such cases itself, so its check is switched off to reach the compiler."""
    from pythonarchtesting.principles import task as task_module

    monkeypatch.setattr(task_module, "_cases_problem", lambda *args: None)
    task = tmp_path / "io_separation"
    shutil.copytree(
        _EXAMPLES / "io_separation", task, ignore=shutil.ignore_patterns("assignments")
    )
    toml = task / "task.toml"
    old = '"grades.format_summary" = [{ args = [[1, 2, 3, 1]] }]'
    text = toml.read_text(encoding="utf-8")
    assert old in text
    toml.write_text(text.replace(old, old[:-3] + ", expected = 9 }]"), encoding="utf-8")

    result = prepare_task(str(task), sandbox="limits")

    assert result["accepted"] is False
    [problem] = result["problems"]
    assert problem.startswith("compiler_invalid_param on grades.format_summary:")
    assert "unknown keys: expected" in problem
