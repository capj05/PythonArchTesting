"""The MCP tools of global mode: ``discover_roles``, ``prepare_global_task``
and ``run_global_evaluation``. Nothing here runs a submission: the tools are
checked on what they bind and write; the runs are in
``tests/integration/test_global_mode.py``."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import anyio
import pytest

from pythonarchtesting.global_mode.model import RoleDiscovery
from pythonarchtesting.global_mode.selftask import SelfTask
from pythonarchtesting.mcp_server import global_tools
from pythonarchtesting.mcp_server.errors import ToolInputError

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "global_mode"
SPACE_A = FIXTURES / "space_a"

GLOBAL_TOOLS = {
    "discover_roles": ["submission", "principles", "assignment"],
    "prepare_global_task": [
        "submission",
        "principle",
        "cases",
        "out_dir",
        "overrides",
    ],
    "run_global_evaluation": ["submission", "task_dirs", "output_dir", "sandbox"],
}

_POLY_CASES: dict[str, list] = {
    "actions.total_power": [
        {"args": [[{"$new": "ship.Reactor"}, {"$new": "ship.SolarPanel"}]]},
        {"args": [[]]},
    ]
}


def _server() -> Any:
    pytest.importorskip("mcp")
    from pythonarchtesting.mcp_server import server

    return server


def test_global_tools_registered_with_their_parameters() -> None:
    server = _server()
    tools = {tool.name: tool for tool in anyio.run(server.mcp.list_tools)}

    for name, parameters in GLOBAL_TOOLS.items():
        tool = tools[name]
        assert list(tool.input_schema["properties"]) == parameters, name
        assert tool.annotations is not None
        assert tool.annotations.open_world_hint is False
        assert tool.description and "global mode" in tool.description.lower()
    assert tools["discover_roles"].annotations.read_only_hint is True
    for name in ("prepare_global_task", "run_global_evaluation"):
        assert tools[name].annotations.read_only_hint is False
        assert tools[name].annotations.destructive_hint is False


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("discover_roles", {"submission": "space_a", "principles": ["polymorphism"]}),
        (
            "prepare_global_task",
            {
                "submission": str(SPACE_A),
                "principle": "polymorphism",
                "cases": {},
                "out_dir": "task",
            },
        ),
        (
            "run_global_evaluation",
            {"submission": str(SPACE_A), "task_dirs": ["task"], "output_dir": "/x"},
        ),
    ],
)
def test_relative_path_is_a_tool_error(tool: str, arguments: dict[str, Any]) -> None:
    server = _server()
    from mcp.server.mcpserver.exceptions import ToolError

    async def call() -> Any:
        return await server.mcp.call_tool(tool, arguments)

    with pytest.raises(ToolError, match="must be an absolute path"):
        anyio.run(call)


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("discover_roles", {"submission": "/s", "principles": []}),
        (
            "prepare_global_task",
            {"submission": "/s", "principle": "p", "cases": {}, "out_dir": "/o"},
        ),
    ],
)
def test_scanning_tools_run_off_the_event_loop(
    tool: str, arguments: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A full scan of the submission must not block the server's event loop:
    the tool runs in a worker thread (the SDK runs a sync tool in one, as
    run_global_evaluation does explicitly)."""
    import threading

    server = _server()
    threads: list[threading.Thread] = []

    def record(*args: Any, **kwargs: Any) -> dict[str, Any]:
        threads.append(threading.current_thread())
        return {}

    monkeypatch.setattr(global_tools, tool, record)

    async def call() -> Any:
        return await server.mcp.call_tool(tool, arguments)

    anyio.run(call)
    assert threads and threads[0] is not threading.main_thread()


def test_unknown_principle_is_a_tool_input_error(tmp_path: Path) -> None:
    with pytest.raises(ToolInputError, match="did you mean: encapsulation"):
        global_tools.discover_roles(str(SPACE_A), ["encapsulaton"])
    with pytest.raises(ToolInputError, match="unknown principle"):
        global_tools.prepare_global_task(
            str(SPACE_A), "nonsense", {}, str(tmp_path / "t")
        )


def test_principle_without_discovery_is_a_tool_input_error() -> None:
    with pytest.raises(ToolInputError, match="no role discovery"):
        global_tools.discover_roles(str(SPACE_A), ["strategy"])


def test_discover_roles_lists_the_cases_each_running_entity_needs() -> None:
    result = global_tools.discover_roles(
        str(SPACE_A), ["io_separation", "polymorphism"], assignment="a space game"
    )

    assert result["assignment"] == "a space game"
    assert result["syntax_errors"] == []
    io, poly = result["principles"]
    assert io["roles"]["logic"][0]["entity"] == "actions"
    needed = {n["entity"]: n for n in io["cases_needed"]}
    # The module bound as a whole stands for its public functions.
    assert sorted(needed) == [
        "actions.go",
        "actions.load",
        "actions.status",
        "actions.take",
        "actions.total_power",
        "ui.main",
    ]
    assert needed["ui.main"]["role"] == "io"
    assert "stdin" in needed["ui.main"]["cases"]
    # Base and variants are checked statically: only the client runs.
    assert [n["entity"] for n in poly["cases_needed"]] == ["actions.total_power"]


def test_prepare_global_task_writes_a_task_with_its_discovery(tmp_path: Path) -> None:
    out = tmp_path / "poly"

    result = global_tools.prepare_global_task(
        str(SPACE_A), "polymorphism", _POLY_CASES, str(out)
    )

    assert result["task_dirs"] == [str(out)]
    assert result["task_dir"] == str(out)
    # parts is there for one task too; the flat keys repeat its only part.
    (part,) = result["parts"]
    assert part["task_dir"] == str(out) and part["roles"] == result["roles"]
    assert result["problems"] == [] and result["dropped"] == []
    assert result["ignored_cases"] == []
    assert [b["entity"] for b in result["roles"]["base"]] == ["ship.Module"]
    discovery = RoleDiscovery.from_dict(
        json.loads((out / "discovery.json").read_text(encoding="utf-8"))
    )
    assert discovery.to_dict()["roles"] == result["roles"]
    assert SelfTask.load(out).dropped == ()
    assert (out / "task.toml").is_file()


def test_overrides_reach_the_discovery(tmp_path: Path) -> None:
    result = global_tools.prepare_global_task(
        str(SPACE_A),
        "polymorphism",
        _POLY_CASES,
        str(tmp_path / "t"),
        overrides=[
            {
                "entity": "ship.Reactor",
                "action": "dispute",
                "role": "variant",
                "why": "a helper, not a module of the ship",
            }
        ],
    )

    reactor = next(
        b for b in result["roles"]["variant"] if b["entity"] == "ship.Reactor"
    )
    assert reactor["disputed"] == "a helper, not a module of the ship"


def test_malformed_override_is_a_tool_input_error(tmp_path: Path) -> None:
    with pytest.raises(ToolInputError, match="override 0"):
        global_tools.prepare_global_task(
            str(SPACE_A),
            "polymorphism",
            _POLY_CASES,
            str(tmp_path / "t"),
            overrides=[{"entity": "ship.Reactor"}],
        )


def test_stray_cases_are_ignored_with_a_reason(tmp_path: Path) -> None:
    cases = {
        **_POLY_CASES,
        "ship.Module": [{"args": []}],  # base: a static check runs nothing
        "ui.main": [{"args": [], "stdin": "konec\n"}],  # in no role
        "actions.nothing": [{"args": []}],  # no such entity
    }

    result = global_tools.prepare_global_task(
        str(SPACE_A), "polymorphism", cases, str(tmp_path / "t")
    )

    assert result["problems"] == []
    ignored = {i["entity"]: i["reason"] for i in result["ignored_cases"]}
    assert set(ignored) == {"ship.Module", "ui.main", "actions.nothing"}
    assert "base" in ignored["ship.Module"]
    assert "no such" in ignored["actions.nothing"]
    task_toml = (tmp_path / "t" / "task.toml").read_text(encoding="utf-8")
    assert 'ship.Module" = ' not in task_toml


def test_null_in_cases_names_the_entity_and_case(tmp_path: Path) -> None:
    cases = {"actions.total_power": [{"args": [[]]}, {"args": [None]}]}

    with pytest.raises(ToolInputError, match=r"actions\.total_power.*case 1"):
        global_tools.prepare_global_task(
            str(SPACE_A), "polymorphism", cases, str(tmp_path / "t")
        )


def test_role_module_without_public_function_is_a_problem(tmp_path: Path) -> None:
    sub = tmp_path / "game"
    shutil.copytree(SPACE_A, sub)
    (sub / "helpers.py").write_text("def _hidden(state):\n    return 1\n")

    result = global_tools.prepare_global_task(
        str(sub),
        "io_separation",
        {"ui.main": [{"args": [], "stdin": "konec\n"}]},
        str(tmp_path / "t"),
        overrides=[
            {"entity": "helpers", "action": "add", "role": "logic", "why": "rules"}
        ],
    )

    assert any("no top-level public function" in p for p in result["problems"])


_TWO_HIERARCHIES = '''from abc import ABC, abstractmethod


class Shape(ABC):
    @abstractmethod
    def area(self):
        """Area."""


class Square(Shape):
    def area(self):
        return 4


class Animal(ABC):
    @abstractmethod
    def sound(self):
        """Sound."""


class Dog(Animal):
    def sound(self):
        return "woof"


def total(shapes):
    return sum(s.area() for s in shapes)


def chorus(animals):
    return " ".join(a.sound() for a in animals)
'''


def test_several_bases_give_one_task_per_base(tmp_path: Path) -> None:
    sub = tmp_path / "zoo"
    sub.mkdir()
    (sub / "world.py").write_text(_TWO_HIERARCHIES, encoding="utf-8")
    cases = {
        "world.total": [{"args": [[{"$new": "world.Square"}]]}],
        "world.chorus": [{"args": [[{"$new": "world.Dog"}]]}],
    }

    result = global_tools.prepare_global_task(
        str(sub), "polymorphism", cases, str(tmp_path / "t")
    )

    parts = {p["base"]: p for p in result["parts"]}
    assert set(parts) == {"world.Animal", "world.Shape"}
    assert result["task_dirs"] == [p["task_dir"] for p in result["parts"]]
    assert len(set(result["task_dirs"])) == 2
    shape = parts["world.Shape"]
    assert [b["entity"] for b in shape["roles"]["client"]] == ["world.total"]
    assert shape["problems"] == []
    # The other base's client is no stray: the other part runs it.
    assert result["ignored_cases"] == []
    shape_toml = (Path(shape["task_dir"]) / "task.toml").read_text(encoding="utf-8")
    assert "world.total" in shape_toml and "world.chorus" not in shape_toml
    for task_dir in result["task_dirs"]:
        assert (Path(task_dir) / "discovery.json").is_file()
    assert "task_dir" not in result


def test_run_global_evaluation_rejects_a_dir_without_discovery(tmp_path: Path) -> None:
    with pytest.raises(ToolInputError, match="discovery.json"):
        global_tools.run_global_evaluation(
            str(SPACE_A), [str(tmp_path)], str(tmp_path / "out")
        )


def test_run_global_evaluation_rejects_a_task_of_another_submission(
    tmp_path: Path,
) -> None:
    out = tmp_path / "t"
    global_tools.prepare_global_task(
        str(SPACE_A), "polymorphism", _POLY_CASES, str(out)
    )

    with pytest.raises(ToolInputError, match="prepared for"):
        global_tools.run_global_evaluation(
            str(FIXTURES / "detective_b"), [str(out)], str(tmp_path / "out")
        )


def test_not_applied_principle_is_reported_without_running(tmp_path: Path) -> None:
    sub = FIXTURES / "detective_b"
    task = global_tools.prepare_global_task(
        str(sub), "polymorphism", {}, str(tmp_path / "t")
    )
    assert task["not_applied"]

    summary = global_tools.run_global_evaluation(
        str(sub), task["task_dirs"], str(tmp_path / "out")
    )

    assert summary["counts"]["not_applied"] == 1
    assert summary["principles"][0]["status"] == "not_applied"
    report = Path(summary["report_json"])
    assert report == tmp_path / "out" / "global-report.json"
    assert json.loads(report.read_text(encoding="utf-8"))["counts"] == summary["counts"]


def _copy(tmp_path: Path) -> Path:
    sub = tmp_path / "space_a"
    shutil.copytree(SPACE_A, sub, ignore=shutil.ignore_patterns("__pycache__"))
    return sub


@pytest.mark.parametrize("inside", [True, False])
def test_out_dir_and_submission_must_not_nest(tmp_path: Path, inside: bool) -> None:
    sub = _copy(tmp_path / "work")
    out = sub / "tasks" if inside else tmp_path

    with pytest.raises(ToolInputError, match="out_dir"):
        global_tools.prepare_global_task(
            str(sub), "polymorphism", _POLY_CASES, str(out)
        )
    assert not (sub / "tasks").exists()


@pytest.mark.parametrize("inside", [True, False])
def test_output_dir_and_submission_must_not_nest(tmp_path: Path, inside: bool) -> None:
    sub = _copy(tmp_path / "work")
    task = global_tools.prepare_global_task(
        str(sub), "polymorphism", _POLY_CASES, str(tmp_path / "t")
    )
    out = sub / "out" if inside else tmp_path

    with pytest.raises(ToolInputError, match="output_dir"):
        global_tools.run_global_evaluation(str(sub), task["task_dirs"], str(out))


def test_run_global_evaluation_rejects_duplicate_tasks(tmp_path: Path) -> None:
    first = global_tools.prepare_global_task(
        str(SPACE_A), "polymorphism", _POLY_CASES, str(tmp_path / "a")
    )
    second = global_tools.prepare_global_task(
        str(SPACE_A), "polymorphism", _POLY_CASES, str(tmp_path / "b")
    )

    with pytest.raises(ToolInputError, match="twice"):
        global_tools.run_global_evaluation(
            str(SPACE_A), first["task_dirs"] * 2, str(tmp_path / "out")
        )
    with pytest.raises(ToolInputError, match="polymorphism.*ship.Module"):
        global_tools.run_global_evaluation(
            str(SPACE_A),
            first["task_dirs"] + second["task_dirs"],
            str(tmp_path / "out"),
        )


def test_discover_roles_docstring_shows_init_as_json() -> None:
    server = _server()
    tools = {tool.name: tool for tool in anyio.run(server.mcp.list_tools)}
    description = tools["discover_roles"].description

    assert '"init": {"args": [...]}' in description
    assert 'kind: "method"' in description


def test_not_applied_principle_drops_nothing(tmp_path: Path) -> None:
    # No class holds a container: encapsulation does not apply, so the
    # clients without cases are no unverified entities either.
    sub = tmp_path / "calc"
    sub.mkdir()
    (sub / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    task = global_tools.prepare_global_task(
        str(sub), "encapsulation", {}, str(tmp_path / "t")
    )

    assert task["not_applied"]
    assert task["roles"]["client"]
    assert task["dropped"] == []
    assert task["parts"][0]["dropped"] == []


_NO_CLIENT = """from abc import ABC, abstractmethod


class Shape(ABC):
    @abstractmethod
    def area(self):
        ...


class Square(Shape):
    def area(self):
        return 4


def main():
    print(Square().area())
"""


def test_polymorphism_without_client_cases_is_worded_for_global_mode(
    tmp_path: Path,
) -> None:
    sub = tmp_path / "shapes"
    sub.mkdir()
    (sub / "shapes.py").write_text(_NO_CLIENT, encoding="utf-8")

    task = global_tools.prepare_global_task(
        str(sub), "polymorphism", {}, str(tmp_path / "t")
    )
    summary = global_tools.run_global_evaluation(
        str(sub), task["task_dirs"], str(tmp_path / "out")
    )

    (problem,) = task["problems"]
    assert "[roles]" not in problem and "add client" not in problem
    assert problem.startswith("no client was found, or every client found lacks cases")
    assert "static ones included" in problem
    (outcome,) = summary["principles"]
    assert outcome["status"] == "unverified"
    assert {"reason": "task", "why": problem} in outcome["unverified"]
    assert {"entity": "shapes.main", "role": "client", "reason": "no cases"} in (
        outcome["unverified"]
    )
