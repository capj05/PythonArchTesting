"""Global mode: a submission checked as its own reference.

``write_self_task`` writes a task whose reference is the student's project
itself, so the roles bind the student's own entities and no reference
solution is needed. The existing core runs it unchanged: ``run_evaluation``
over a copy of the submission finds the designed violation, and
``prepare_task`` accepts the self-task of a clean game (whose modules import
each other absolutely, ``from case import State``).

Entity names are relative to the submission root, as the core names them:
``actions.status``, ``ui.main``, ``ship.State``.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.global_mode.discovery import discover_roles
from pythonarchtesting.global_mode.model import BoundEntity, RoleDiscovery
from pythonarchtesting.global_mode.outcome import judge_principle
from pythonarchtesting.global_mode.selftask import _source_entities, write_self_task
from pythonarchtesting.mcp_server import global_tools
from pythonarchtesting.mcp_server.evaluation import run_evaluation
from pythonarchtesting.mcp_server.reports import _findings, load_report
from pythonarchtesting.mcp_server.tasks import prepare_task
from pythonarchtesting.principles.catalog import get_principle

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "global_mode"
EXPECTED = tomllib.loads((FIXTURES / "expected.toml").read_text(encoding="utf-8"))

_SHIP = {"$new": "ship.State"}
_CASE = {"$new": "case.State"}

# One ordinary call per logic function of space_a.actions (the role binds
# the whole module, so every public function needs cases) and a game for
# ui.main that ends on "konec".
SPACE_A_IO_CASES: dict[str, list] = {
    "actions.take": [{"args": [_SHIP, ["take", "crate"]]}, {"args": [_SHIP, ["take"]]}],
    "actions.load": [{"args": [_SHIP, ["load", "crate"]]}, {"args": [_SHIP, ["load"]]}],
    "actions.total_power": [
        {"args": [[{"$new": "ship.Reactor"}, {"$new": "ship.SolarPanel"}]]},
        {"args": [[]]},
    ],
    "actions.status": [{"args": [_SHIP, ["status"]]}],
    "actions.go": [{"args": [_SHIP, ["go", "lab"]]}, {"args": [_SHIP, ["go"]]}],
    "ui.main": [{"args": [], "stdin": "status\nkonec\n"}],
}

DETECTIVE_B_IO_CASES: dict[str, list] = {
    "commands.search": [
        {"args": [_CASE, ["search", "knife"]]},
        {"args": [_CASE, ["search"]]},
    ],
    "commands.walk": [{"args": [_CASE, ["walk", "hall"]]}, {"args": [_CASE, ["walk"]]}],
    "commands.notes": [{"args": [_CASE, ["notes"]]}],
    "console.run": [
        {"args": [], "stdin": "search knife\nnotes\nwalk hall\n\nxyz\nkonec\n"},
        {"args": [], "stdin": "notes\n"},
    ],
}


def test_self_task_finds_print_in_logic_of_space_a(tmp_path: Path) -> None:
    sub = FIXTURES / "space_a"
    task = write_self_task(
        sub,
        "io_separation",
        roles={"logic": ["actions"], "io": ["ui.main"]},
        cases=SPACE_A_IO_CASES,
        out_dir=tmp_path / "task",
    )
    assert task.dropped == ()
    copy = tmp_path / "target" / "space_a"
    shutil.copytree(sub, copy)

    run = run_evaluation(
        str(task.task_dir),
        str(tmp_path / "out"),
        targets=[str(copy)],
        dynamic=True,
        sandbox="limits",
    )

    report = load_report(run["report_json"])
    found = {
        f.error_id
        for f in _findings(get_principle("io_separation"), report["targets"][0])
    }
    assert "print_instead_of_return" in found


def test_prepare_task_accepts_self_task_of_clean_game(tmp_path: Path) -> None:
    task = write_self_task(
        FIXTURES / "detective_b",
        "io_separation",
        roles={"logic": ["commands"], "io": ["console.run"]},
        cases=DETECTIVE_B_IO_CASES,
        out_dir=tmp_path / "t",
    )

    result = prepare_task(str(task.task_dir), sandbox="limits")

    assert result["problems"] == [], result
    assert result["reference_passes"] is True, result
    assert {e["status"] for e in result["errors"]} <= {
        "killed",
        "not_applicable",
        "gap",
        "not_verifiable_by_mutation",
    }, result


def _io_discovery(logic: str, io: str) -> RoleDiscovery:
    return RoleDiscovery(
        principle="io_separation",
        roles={
            "logic": (BoundEntity(logic, "code", "no print or input"),),
            "io": (BoundEntity(io, "code", "reads input()"),),
        },
        conflicts=(),
        not_applied=None,
    )


def test_judge_principle_space_a_io_is_violated(tmp_path: Path) -> None:
    sub = FIXTURES / "space_a"
    expected = EXPECTED["space_a"]["io_separation"]
    task = write_self_task(
        sub,
        "io_separation",
        roles=expected["roles"],
        cases=SPACE_A_IO_CASES,
        out_dir=tmp_path / "task",
    )

    outcome = judge_principle(
        sub,
        _io_discovery("actions", "ui.main"),
        task,
        tmp_path / "work",
        sandbox="limits",
    )

    assert outcome.status == expected["status"]
    assert {f["error_id"] for f in outcome.findings} == set(expected["errors"])
    # status prints three times: three findings, one entity in violation.
    assert len(outcome.findings) == 3
    assert (outcome.sites, outcome.violations) == (6, 1)
    assert outcome.mutation is None
    assert outcome.unclassified == ()
    assert (tmp_path / "work" / "target" / "space_a" / "actions.py").is_file()


def test_judge_principle_detective_b_io_is_ok(tmp_path: Path) -> None:
    sub = FIXTURES / "detective_b"
    expected = EXPECTED["detective_b"]["io_separation"]
    task = write_self_task(
        sub,
        "io_separation",
        roles=expected["roles"],
        cases=DETECTIVE_B_IO_CASES,
        out_dir=tmp_path / "task",
    )

    outcome = judge_principle(
        sub,
        _io_discovery("commands", "console.run"),
        task,
        tmp_path / "work",
        sandbox="limits",
    )

    assert outcome.status == expected["status"], outcome.to_dict()
    assert outcome.findings == () and outcome.unverified == ()
    assert outcome.violations == 0 and outcome.sites == 4
    assert outcome.mutation is not None
    assert outcome.mutation["print_instead_of_return"] == "killed"
    assert outcome.coverage is not None and outcome.coverage >= 0.8


def test_judge_principle_unclassified_call_blocks_mutation_as_unverified(
    tmp_path: Path,
) -> None:
    # A call no typical error explains (io.open_code) in a logic function:
    # never violated, but the check fails on the reference (the submission
    # itself), so no mutant verifies its errors and the cause is named.
    sub = tmp_path / "detective_b"
    shutil.copytree(FIXTURES / "detective_b", sub)
    commands = sub / "commands.py"
    commands.write_text(
        "import io\n\n\n"
        + commands.read_text(encoding="utf-8").replace(
            "def notes(state, words):\n",
            "def notes(state, words):\n    io.open_code(__file__).close()\n",
        ),
        encoding="utf-8",
    )
    task = write_self_task(
        sub,
        "io_separation",
        roles={"logic": ["commands"], "io": ["console.run"]},
        cases=DETECTIVE_B_IO_CASES,
        out_dir=tmp_path / "task",
    )

    outcome = judge_principle(
        sub,
        _io_discovery("commands", "console.run"),
        task,
        tmp_path / "work",
        sandbox="limits",
    )

    assert outcome.status == "unverified", outcome.to_dict()
    assert outcome.findings == () and outcome.violations == 0
    assert {u["target"] for u in outcome.unclassified} == {"commands:notes"}
    blocked = [u for u in outcome.unverified if u.get("because")]
    assert blocked and all(
        u["reason"] == "mutation:reference_fails"
        and u["because"] == "unclassified findings"
        and u["entities"] == ["commands.notes"]
        for u in blocked
    )
    assert "print_instead_of_return" in {u["error"] for u in blocked}
    # The task problem is folded into those entries, not listed again.
    assert not any(u["reason"] == "task" for u in outcome.unverified)


# Cases for the encapsulation clients of space_a: each action and the game
# on a fresh ship state (take and load change its cargo), and each method.
SPACE_A_ENCAPSULATION_CASES: dict[str, list] = {
    **{name: SPACE_A_IO_CASES[name] for name in SPACE_A_IO_CASES if name != "ui.main"},
    "ui.main": [{"args": [], "stdin": "take crate\nload box\nstatus\nkonec\n"}],
    "ship.State.go_to": [{"args": ["lab"]}],
    "ship.Reactor.power": [{"args": []}],
    "ship.SolarPanel.power": [{"args": []}],
}
SPACE_A_ENCAPSULATION_INIT: dict[str, dict] = {
    "ship.State.go_to": {"args": []},
    "ship.Reactor.power": {"args": []},
    "ship.SolarPanel.power": {"args": []},
}


def test_judge_principle_space_a_encapsulation_is_violated(tmp_path: Path) -> None:
    sub = FIXTURES / "space_a"
    expected = EXPECTED["space_a"]["encapsulation"]
    discovery = discover_roles("encapsulation", _source_entities(sub))
    assert [b.entity for b in discovery.roles["owner"]] == expected["roles"]["owner"]
    clients = [b.entity for b in discovery.roles["client"]]
    assert clients == [
        "actions",
        "ship.Reactor.power",
        "ship.SolarPanel.power",
        "ship.State.go_to",
        "ui",
    ]
    task = write_self_task(
        sub,
        "encapsulation",
        roles={"owner": expected["roles"]["owner"], "client": clients},
        cases=SPACE_A_ENCAPSULATION_CASES,
        out_dir=tmp_path / "task",
        init=SPACE_A_ENCAPSULATION_INIT,
    )
    assert task.dropped == ()

    outcome = judge_principle(sub, discovery, task, tmp_path / "work", sandbox="limits")

    assert outcome.status == expected["status"], outcome.to_dict()
    assert {f["error_id"] for f in outcome.findings} == set(expected["errors"])
    # Only actions.take writes the cargo's private list from outside; the
    # other clients, the game loop among them, pass.
    assert [f["target"] for f in outcome.findings] == ["actions:take"]
    assert (outcome.sites, outcome.violations) == (9, 1)
    assert outcome.unverified == () and outcome.unclassified == ()


# Cases for the encapsulation clients of detective_b: each command and the
# game on a fresh case state (search changes the pocket), the game also with
# a clue found twice, which the pocket refuses, an empty line, an unknown
# command and an input that ends without konec; and the state's own method.
DETECTIVE_B_ENCAPSULATION_CASES: dict[str, list] = {
    **{n: DETECTIVE_B_IO_CASES[n] for n in DETECTIVE_B_IO_CASES if n != "console.run"},
    "console.run": [
        {"args": [], "stdin": "search knife\nsearch knife\nnotes\nwalk hall\nkonec\n"},
        {"args": [], "stdin": "\nxyz\nsearch\n"},
    ],
    "case.State.go_to": [{"args": ["hall"]}],
}


def test_judge_principle_detective_b_encapsulation_is_ok(tmp_path: Path) -> None:
    sub = FIXTURES / "detective_b"
    expected = EXPECTED["detective_b"]["encapsulation"]
    discovery = discover_roles("encapsulation", _source_entities(sub))
    assert [b.entity for b in discovery.roles["owner"]] == expected["roles"]["owner"]
    clients = [b.entity for b in discovery.roles["client"]]
    assert clients == ["case.State.go_to", "commands", "console"]
    task = write_self_task(
        sub,
        "encapsulation",
        roles={"owner": expected["roles"]["owner"], "client": clients},
        cases=DETECTIVE_B_ENCAPSULATION_CASES,
        out_dir=tmp_path / "task",
        init={"case.State.go_to": {"args": []}},
    )
    assert task.dropped == ()

    outcome = judge_principle(sub, discovery, task, tmp_path / "work", sandbox="limits")

    assert outcome.status == expected["status"], outcome.to_dict()
    assert outcome.findings == () and outcome.unverified == ()
    assert outcome.coverage is not None and outcome.coverage >= 0.8
    assert outcome.mutation is not None
    assert set(outcome.mutation) == {
        "bypass_method",
        "mutate_container",
        "replace_attribute",
        "read_private",
    }


_OUTSIDE_WORLD = """class Inventory:
    def __init__(self):
        self.items = []

    def show(self):
        return ", ".join(self.items)


class State:
    def __init__(self):
        self.inventory = Inventory()
"""
_OUTSIDE_ACTIONS = """def take(state, item):
    state.inventory.items.append(item)
    return "You take the " + item + "."
"""


def test_judge_principle_container_changed_only_from_outside_is_violated(
    tmp_path: Path,
) -> None:
    # Inventory changes its list in no method of its own: only the action
    # appends to it from outside, which alone makes Inventory the owner.
    sub = tmp_path / "game"
    sub.mkdir()
    (sub / "world.py").write_text(_OUTSIDE_WORLD, encoding="utf-8")
    (sub / "actions.py").write_text(_OUTSIDE_ACTIONS, encoding="utf-8")
    discovery = discover_roles("encapsulation", _source_entities(sub))
    assert [b.entity for b in discovery.roles["owner"]] == ["world.Inventory"]
    assert [b.entity for b in discovery.roles["client"]] == ["actions"]
    task = write_self_task(
        sub,
        "encapsulation",
        roles={"owner": ["world.Inventory"], "client": ["actions"]},
        cases={"actions.take": [{"args": [{"$new": "world.State"}, "knife"]}]},
        out_dir=tmp_path / "task",
    )
    assert task.dropped == ()

    outcome = judge_principle(sub, discovery, task, tmp_path / "work", sandbox="limits")

    assert outcome.status == "violated", outcome.to_dict()
    assert {f["error_id"] for f in outcome.findings} == {"mutate_container"}
    assert [f["target"] for f in outcome.findings] == ["actions:take"]


# Global mode through its MCP tools, as the teacher's AI client calls them:
# discover_roles, then cases written for what it lists (here by hand, as the
# AI would), prepare_global_task per principle, run_global_evaluation.

_INIT = {"init": {"args": []}}
SPACE_A_POLYMORPHISM_CASES: dict[str, list] = {
    "actions.total_power": SPACE_A_IO_CASES["actions.total_power"],
}
SPACE_A_GLOBAL_CASES: dict[str, dict[str, list]] = {
    "io_separation": SPACE_A_IO_CASES,
    "polymorphism": SPACE_A_POLYMORPHISM_CASES,
    # The methods' objects are built with no arguments (a case's own init).
    "encapsulation": {
        name: (
            [{**case, **_INIT} for case in cases]
            if name in SPACE_A_ENCAPSULATION_INIT
            else cases
        )
        for name, cases in SPACE_A_ENCAPSULATION_CASES.items()
    },
}
PRINCIPLES = ["io_separation", "polymorphism", "encapsulation"]


def _prepare_all(
    sub: Path, tmp_path: Path, cases: dict[str, dict[str, list]]
) -> tuple[dict[str, Any], list[str]]:
    discovered = global_tools.discover_roles(str(sub), PRINCIPLES)
    task_dirs: list[str] = []
    for principle in PRINCIPLES:
        prepared = global_tools.prepare_global_task(
            str(sub), principle, cases[principle], str(tmp_path / "tasks" / principle)
        )
        task_dirs.extend(prepared["task_dirs"])
    return discovered, task_dirs


def test_space_a_all_three_principles_end_to_end(tmp_path: Path) -> None:
    sub = FIXTURES / "space_a"
    discovered, task_dirs = _prepare_all(sub, tmp_path, SPACE_A_GLOBAL_CASES)
    for found in discovered["principles"]:
        # The AI wrote cases for exactly what discovery asked for.
        needed = {n["entity"] for n in found["cases_needed"]}
        assert needed == set(SPACE_A_GLOBAL_CASES[found["principle"]])

    summary = global_tools.run_global_evaluation(
        str(sub), task_dirs, str(tmp_path / "out"), sandbox="limits"
    )

    report = json.loads(
        (tmp_path / "out" / "global-report.json").read_text(encoding="utf-8")
    )
    assert report["principles"] == summary["principles"]
    outcomes = {p["principle"]: p for p in summary["principles"]}
    assert list(outcomes) == PRINCIPLES
    for principle, outcome in outcomes.items():
        expected = EXPECTED["space_a"][principle]
        assert outcome["status"] == expected["status"], outcome
        assert {f["error_id"] for f in outcome["findings"]} == set(
            expected.get("errors", [])
        ), outcome
        for role, names in expected["roles"].items():
            assert [b["entity"] for b in outcome["roles"][role]] == names
    assert summary["counts"] == {
        "not_applied": 0,
        "ok": 1,
        "unverified": 0,
        "violated": 2,
    }
    assert {tuple(f["principles"]) for f in summary["findings"]} == {
        ("io_separation",),
        ("encapsulation",),
    }


def _copy_space_a(tmp_path: Path) -> Path:
    sub = tmp_path / "space_a"
    shutil.copytree(
        FIXTURES / "space_a", sub, ignore=shutil.ignore_patterns("__pycache__")
    )
    return sub


def test_syntax_error_submission_is_unverified_for_every_principle(
    tmp_path: Path,
) -> None:
    sub = _copy_space_a(tmp_path)
    ship = sub / "ship.py"
    ship.write_text(
        ship.read_text(encoding="utf-8") + "\n\ndef broken(:\n    pass\n",
        encoding="utf-8",
    )

    lines = ship.read_text(encoding="utf-8").splitlines()
    broken_line = lines.index("def broken(:") + 1

    discovered, task_dirs = _prepare_all(sub, tmp_path, SPACE_A_GLOBAL_CASES)
    summary = global_tools.run_global_evaluation(
        str(sub), task_dirs, str(tmp_path / "out"), sandbox="limits"
    )

    assert [e["file"] for e in discovered["syntax_errors"]] == ["ship.py"]
    assert [p["principle"] for p in summary["principles"]] == PRINCIPLES
    for outcome in summary["principles"]:
        assert outcome["status"] == "unverified", outcome
        reasons = [u for u in outcome["unverified"] if u["reason"] == "syntax_error"]
        assert reasons and reasons[0]["file"] == "ship.py"
        assert reasons[0]["line"] == broken_line
    assert summary["counts"]["unverified"] == 3


_ENDLESS = (
    "        except EOFError:\n            continue\n"  # never ends without konec
)


def test_endless_input_loop_is_unverified_not_hanging(tmp_path: Path) -> None:
    sub = _copy_space_a(tmp_path)
    ui = sub / "ui.py"
    text = ui.read_text(encoding="utf-8")
    assert "        except EOFError:\n            break\n" in text
    ui.write_text(
        text.replace("        except EOFError:\n            break\n", _ENDLESS),
        encoding="utf-8",
    )
    # The logic returns its text, so the loop is the only thing left to find.
    actions = sub / "actions.py"
    actions.write_text(
        actions.read_text(encoding="utf-8").replace(
            '    print("Room:", state.room)\n'
            '    print("Crates:", state.cargo.count())\n'
            '    print("Power:", total_power(state.modules))\n'
            '    return ""\n',
            '    return "Room: " + state.room\n',
        ),
        encoding="utf-8",
    )
    cases = {**SPACE_A_IO_CASES, "ui.main": [{"args": [], "stdin": "status\n"}]}
    started = time.monotonic()

    prepared = global_tools.prepare_global_task(
        str(sub), "io_separation", cases, str(tmp_path / "task")
    )
    summary = global_tools.run_global_evaluation(
        str(sub), prepared["task_dirs"], str(tmp_path / "out"), sandbox="limits"
    )

    assert time.monotonic() - started < 30
    (outcome,) = summary["principles"]
    assert outcome["status"] == "unverified", outcome
    assert outcome["findings"] == []
    assert {"entity": "ui.main", "reason": "probe_timeout"} in outcome["unverified"]


def test_dispatched_action_reading_input_is_unverified_until_moved(
    tmp_path: Path,
) -> None:
    # status reads the keyboard and ui.COMMANDS dispatches it: discovery
    # keeps it io (it cannot tell an action from the UI) but disputes it, so
    # the principle cannot be ok; the AI's move makes it logic, and the run
    # then finds input_in_logic.
    sub = _copy_space_a(tmp_path)
    actions = sub / "actions.py"
    actions.write_text(
        actions.read_text(encoding="utf-8").replace(
            '    print("Room:", state.room)\n', '    print("Room:", input("where? "))\n'
        ),
        encoding="utf-8",
    )
    cases = {
        **SPACE_A_IO_CASES,
        "actions.status": [
            {**case, "stdin": "lab\n"} for case in SPACE_A_IO_CASES["actions.status"]
        ],
    }

    kept = global_tools.prepare_global_task(
        str(sub), "io_separation", cases, str(tmp_path / "kept")
    )
    status = next(b for b in kept["roles"]["io"] if b["entity"] == "actions.status")
    assert status["disputed"].startswith("possibly input_in_logic")
    summary = global_tools.run_global_evaluation(
        str(sub), kept["task_dirs"], str(tmp_path / "out1"), sandbox="limits"
    )
    (outcome,) = summary["principles"]
    assert outcome["status"] == "unverified", outcome
    assert {"actions.status"} == {
        u["entity"] for u in outcome["unverified"] if u["reason"] == "role_disputed"
    }

    moved = global_tools.prepare_global_task(
        str(sub),
        "io_separation",
        cases,
        str(tmp_path / "moved"),
        overrides=[
            {
                "entity": "actions.status",
                "action": "move",
                "role": "io",
                "to_role": "logic",
                "why": "status is a game action of the assignment",
            }
        ],
    )
    assert moved["conflicts"] == []
    summary = global_tools.run_global_evaluation(
        str(sub), moved["task_dirs"], str(tmp_path / "out2"), sandbox="limits"
    )
    (outcome,) = summary["principles"]
    assert outcome["status"] == "violated", outcome
    assert "input_in_logic" in {f["error_id"] for f in outcome["findings"]}


_ROOM = {"room": "hall", "items": []}
GARDEN_C_IO_CASES: dict[str, list] = {
    "actions.go": [{"args": [_ROOM, "north"]}, {"args": [_ROOM, "west"]}],
    "actions.take": [
        {"args": [_ROOM, "key"]},
        {"args": [{"room": "lab", "items": ["a"]}, "b"]},
    ],
    "actions.new_state": [{"args": []}],
    "ui.parse": [{"args": ["go north"]}, {"args": ["look"]}],
    "ui.play": [
        {"args": [_ROOM], "stdin": "go north\nquit\n"},
        {"args": [_ROOM], "stdin": "dance\ntake key\nquit\n"},
    ],
    "main.main": [{"stdin": "go north\nquit\n"}, {"stdin": "dance\ntake key\nquit\n"}],
}


def test_clean_functional_game_loop_is_not_disputed_and_ok(tmp_path: Path) -> None:
    # ui.play reads the keyboard beside the pure ui.parse and main.main calls
    # it, but it is the game loop: not disputed, so the clean game is ok.
    sub = FIXTURES / "garden_c"
    expected = EXPECTED["garden_c"]["io_separation"]

    prepared = global_tools.prepare_global_task(
        str(sub), "io_separation", GARDEN_C_IO_CASES, str(tmp_path / "task")
    )
    assert all("disputed" not in b for b in prepared["roles"]["io"])
    assert prepared["problems"] == [] and prepared["ignored_cases"] == []
    summary = global_tools.run_global_evaluation(
        str(sub), prepared["task_dirs"], str(tmp_path / "out"), sandbox="limits"
    )

    (outcome,) = summary["principles"]
    assert outcome["status"] == expected["status"], outcome
    for role, names in expected["roles"].items():
        assert [b["entity"] for b in outcome["roles"][role]] == names


# Clean projects in shapes that once came out as a false logic_in_main
# (require_runtime_calls): a missing call is evidence only when every case of
# the io entity shows it, and logic is only what the io calls directly.


def _run_io(sub: Path, cases: dict[str, list], tmp_path: Path) -> dict[str, Any]:
    prepared = global_tools.prepare_global_task(
        str(sub), "io_separation", cases, str(tmp_path / "task")
    )
    assert prepared["problems"] == [] and prepared["dropped"] == [], prepared
    assert prepared["ignored_cases"] == [], prepared
    summary = global_tools.run_global_evaluation(
        str(sub), prepared["task_dirs"], str(tmp_path / "out"), sandbox="limits"
    )
    (outcome,) = summary["principles"]
    return outcome


def _assert_roles(outcome: dict[str, Any], expected: dict[str, Any]) -> None:
    for role, names in expected["roles"].items():
        assert [b["entity"] for b in outcome["roles"][role]] == names, outcome


def test_quit_only_case_of_the_io_is_unverified_not_violated(tmp_path: Path) -> None:
    # (a) The AI adds a case that quits at once: console.run then calls no
    # logic in that case, but did in the others.
    sub = FIXTURES / "detective_b"
    cases = {
        **DETECTIVE_B_IO_CASES,
        "console.run": [
            *DETECTIVE_B_IO_CASES["console.run"],
            {"args": [], "stdin": "konec\n"},
        ],
    }

    outcome = _run_io(sub, cases, tmp_path)

    assert outcome["status"] == "unverified", outcome
    assert outcome["findings"] == []
    (missed,) = [
        u for u in outcome["unverified"] if u["reason"] == "missing_call_in_some_cases"
    ]
    assert missed == {
        "entity": "console.run",
        "reason": "missing_call_in_some_cases",
        "error": "logic_in_main",
        "module": "commands",
        "cases": [2],
        "case_count": 3,
    }


_WORLD = {"room": "hall", "items": ["lamp"], "bag": []}
ROOMS_D_IO_CASES: dict[str, list] = {
    "game.new_world": [{"args": []}],
    "game.look": [{"args": [_WORLD]}],
    "game.take": [{"args": [_WORLD, "lamp"]}, {"args": [_WORLD, "sword"]}],
    "ui.main": [
        {"args": [], "stdin": "look\ntake lamp\ntake sword\ndance\n"},
        {"args": [], "stdin": ""},
    ],
}


def test_layered_game_is_not_violated(tmp_path: Path) -> None:
    # (b) ui calls game, game calls rules: rules is no logic of its own, so
    # ui.main need not call it.
    sub = FIXTURES / "rooms_d"
    expected = EXPECTED["rooms_d"]["io_separation"]

    outcome = _run_io(sub, ROOMS_D_IO_CASES, tmp_path)

    _assert_roles(outcome, expected)
    assert outcome["status"] == expected["status"], outcome


def test_student_test_file_is_no_role(tmp_path: Path) -> None:
    # (b) with the student's own test beside the game: not discovered.
    sub = tmp_path / "rooms_d"
    shutil.copytree(
        FIXTURES / "rooms_d", sub, ignore=shutil.ignore_patterns("__pycache__")
    )
    (sub / "test_game.py").write_text(
        "from game import new_world, take\n\n\n"
        "def test_take():\n"
        "    world = new_world()\n"
        "    assert take(world, 'lamp') == 'Taken.'\n"
        "    assert world['bag'] == ['lamp']\n",
        encoding="utf-8",
    )
    expected = EXPECTED["rooms_d"]["io_separation"]

    outcome = _run_io(sub, ROOMS_D_IO_CASES, tmp_path)

    _assert_roles(outcome, expected)
    assert outcome["status"] == expected["status"], outcome


def test_input_and_output_helpers_are_not_violated(tmp_path: Path) -> None:
    # (c) ui.ask and ui.show call nothing of the project: no role, so no
    # check asks them to call the logic.
    sub = FIXTURES / "lantern_e"
    expected = EXPECTED["lantern_e"]["io_separation"]
    cases = {name: c for name, c in ROOMS_D_IO_CASES.items()}

    outcome = _run_io(sub, cases, tmp_path)

    _assert_roles(outcome, expected)
    assert outcome["status"] == expected["status"], outcome


_GAME = {"init": {"args": []}}
# The probe records no call of run to a method of its own class
# (self.execute): each case of run reaches Player, so that it calls into game.
TAVERN_F_IO_CASES: dict[str, list] = {
    "game.Game.run": [
        {
            **_GAME,
            "args": [],
            "stdin": "use key\nuse potion\nhealth\nuse map\ndance\nquit\n",
        },
        {**_GAME, "args": [], "stdin": "use map\n"},
    ],
    "game.Game.execute": [{**_GAME, "args": ["health"]}, {**_GAME, "args": ["dance"]}],
    "game.Game.use": [{**_GAME, "args": ["potion"]}, {**_GAME, "args": ["map"]}],
    "game.Game.health": [{**_GAME, "args": [""]}],
}


def test_oo_game_run_with_self_ask_is_not_violated(tmp_path: Path) -> None:
    # (d) Game().run() in the __main__ block is the entry point and reads
    # through the pure helper self.ask(); the abstract Item.use is no logic.
    sub = FIXTURES / "tavern_f"
    expected = EXPECTED["tavern_f"]["io_separation"]

    outcome = _run_io(sub, TAVERN_F_IO_CASES, tmp_path)

    _assert_roles(outcome, expected)
    assert outcome["status"] == expected["status"], outcome


def test_ok_lists_lines_no_case_ran(tmp_path: Path) -> None:
    # The cases never take anything, so take's success branch never runs:
    # the outcome names its lines whatever the status.
    cases = {
        **ROOMS_D_IO_CASES,
        "game.take": [{"args": [_WORLD, "sword"]}],
        "ui.main": [{"args": [], "stdin": "look\ntake sword\ndance\n"}],
    }

    outcome = _run_io(FIXTURES / "rooms_d", cases, tmp_path)

    take = next(u for u in outcome["unexercised"] if u["entity"] == "game.take")
    assert take["file"] == "game.py"
    assert take["lines"] == [14, 15, 16]


MARKET_G_IO_CASES: dict[str, list] = {
    "goods.buy": [
        {"args": [{"apple": 3}, []], "stdin": "apple\n"},
        {"args": [{"apple": 3}, []], "stdin": "pear\n"},
    ],
    "goods.prices": [{"args": [{"apple": 3, "bread": 5}]}],
    "stall.run": [
        {"args": [], "stdin": "prices\nbuy\napple\nleave\n"},
        {"args": [], "stdin": "buy\npear\nprices\nleave\n"},
    ],
}


def test_input_action_called_by_name_is_unverified_until_moved(tmp_path: Path) -> None:
    # goods.buy reads the keyboard and calls nothing of the project; the loop
    # calls it by name from an if/elif chain. It is no helper (goods has no
    # other io), so it stays io and disputed: never a silent ok. Moved to
    # logic, the run finds input_in_logic.
    sub = FIXTURES / "market_g"
    expected = EXPECTED["market_g"]["io_separation"]

    outcome = _run_io(sub, MARKET_G_IO_CASES, tmp_path / "kept")

    _assert_roles(outcome, expected)
    assert outcome["status"] == expected["status"], outcome
    assert {
        u["reason"] for u in outcome["unverified"] if u.get("entity") == "goods.buy"
    } == {
        "role_disputed",
        "missing_call_role_disputed",
    }

    moved = global_tools.prepare_global_task(
        str(sub),
        "io_separation",
        MARKET_G_IO_CASES,
        str(tmp_path / "moved"),
        overrides=[
            {
                "entity": "goods.buy",
                "action": "move",
                "role": "io",
                "to_role": "logic",
                "why": "buy is a game action of the assignment",
            }
        ],
    )
    assert moved["conflicts"] == []
    summary = global_tools.run_global_evaluation(
        str(sub), moved["task_dirs"], str(tmp_path / "out2"), sandbox="limits"
    )
    (outcome,) = summary["principles"]
    assert outcome["status"] == "violated", outcome
    assert "input_in_logic" in {f["error_id"] for f in outcome["findings"]}


_HARBOR = {"boats": ["skiff"], "moored": []}
HARBOR_H_IO_CASES: dict[str, list] = {
    "boats.moor": [{"args": [_HARBOR, "skiff"]}, {"args": [_HARBOR, "raft"]}],
    "boats.list_boats": [{"args": [_HARBOR]}],
    "dock.main": [{"args": [], "stdin": "boats\nmoor skiff\nmoor raft\nsail\n\n"}],
}


def test_dispatch_table_imported_from_another_module_is_ok(tmp_path: Path) -> None:
    # dock.main looks its order up in orders.ORDERS, which holds the boats
    # functions: boats is the logic, every case of it counts.
    sub = FIXTURES / "harbor_h"
    expected = EXPECTED["harbor_h"]["io_separation"]

    outcome = _run_io(sub, HARBOR_H_IO_CASES, tmp_path)

    _assert_roles(outcome, expected)
    assert outcome["status"] == expected["status"], outcome


_CABIN = {"init": {"args": []}}
CABIN_I_IO_CASES: dict[str, list] = {
    "cabin.Cabin.walk": [{**_CABIN, "args": ["shed"]}, {**_CABIN, "args": ["moon"]}],
    "cabin.Cabin.light": [{**_CABIN, "args": []}],
    "cabin.Cabin.handle": [
        {**_CABIN, "args": ["walk hearth"]},
        {**_CABIN, "args": ["light"]},
        {**_CABIN, "args": ["sleep"]},
        {**_CABIN, "args": ["dance"]},
    ],
    "cabin.Cabin.run": [
        {**_CABIN, "args": [], "stdin": "walk hearth\nlight\nsleep\n"},
        {**_CABIN, "args": [], "stdin": "light\nsleep\n"},
    ],
}


def test_single_class_game_is_unverified_not_violated(tmp_path: Path) -> None:
    # Cabin.run calls self.handle(...), which calls self.walk and self.light:
    # the run records no call to a method of its own class, so run's missing
    # call into cabin is no evidence of logic_in_main.
    sub = FIXTURES / "cabin_i"
    expected = EXPECTED["cabin_i"]["io_separation"]

    prepared = global_tools.prepare_global_task(
        str(sub), "io_separation", CABIN_I_IO_CASES, str(tmp_path / "task")
    )
    summary = global_tools.run_global_evaluation(
        str(sub), prepared["task_dirs"], str(tmp_path / "out"), sandbox="limits"
    )
    (outcome,) = summary["principles"]

    _assert_roles(outcome, expected)
    assert outcome["status"] == expected["status"], outcome
    assert outcome["findings"] == []
    (unobserved,) = [
        u
        for u in outcome["unverified"]
        if u["reason"] == "missing_call_self_calls_unobserved"
    ]
    assert unobserved == {
        "entity": "cabin.Cabin.run",
        "reason": "missing_call_self_calls_unobserved",
        "error": "logic_in_main",
        "module": "cabin",
        "logic": ["cabin.Cabin.handle"],
    }


FORGE_J_IO_CASES: dict[str, list] = {
    "anvil.forge": [{"args": [["iron"], "iron"]}, {"args": [["iron"], "gold"]}],
    "anvil.rack": [{"args": [["iron", "bronze"]]}],
    "smithy.main": [
        {"args": [], "stdin": "rack\nforge iron\nclose\n"},
        {"args": [], "stdin": "forge gold\nrack\nclose\n"},
    ],
}


def test_print_only_module_is_no_logic(tmp_path: Path) -> None:
    # banner only prints what smithy.main hands it and returns nothing: user
    # interface, not a logic that prints instead of returning.
    sub = FIXTURES / "forge_j"
    expected = EXPECTED["forge_j"]["io_separation"]

    outcome = _run_io(sub, FORGE_J_IO_CASES, tmp_path)

    _assert_roles(outcome, expected)
    assert outcome["status"] == expected["status"], outcome


def test_print_in_a_helper_of_the_logic_stays_violated(tmp_path: Path) -> None:
    # rules.can_take of the layered game prints before it returns, reached
    # through game.take: output_through_helper, whatever the print-only rule.
    sub = tmp_path / "rooms_d"
    shutil.copytree(
        FIXTURES / "rooms_d", sub, ignore=shutil.ignore_patterns("__pycache__")
    )
    (sub / "rules.py").write_text(
        "def can_take(items, name):\n"
        "    if name not in items:\n"
        "        print('There is no ' + name + ' here.')\n"
        "    return name in items\n",
        encoding="utf-8",
    )
    expected = EXPECTED["rooms_d"]["io_separation"]

    outcome = _run_io(sub, ROOMS_D_IO_CASES, tmp_path)

    _assert_roles(outcome, expected)
    assert outcome["status"] == "violated", outcome
    assert {f["error_id"] for f in outcome["findings"]} == {"output_through_helper"}


def _write(root: Path, files: dict[str, str]) -> Path:
    root.mkdir()
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


_PANTRY = {"shelf": ["jam"], "basket": []}
_PANTRY_DEEDS = (
    "def peek(pantry):\n    return 'On the shelf: ' + ', '.join(pantry['shelf'])\n\n\n"
    "def fetch(pantry, thing):\n"
    "    if thing in pantry['shelf']:\n"
    "        pantry['shelf'].remove(thing)\n"
    "        pantry['basket'].append(thing)\n"
    "        return 'Fetched ' + thing + '.'\n"
    "    return 'No ' + thing + '.'\n"
)


def test_lone_input_helper_module_is_ok(tmp_path: Path) -> None:
    # prompts.ask only reads the keyboard and its module has no logic: a
    # helper of the user interface, in no role.
    sub = _write(
        tmp_path / "pantry",
        {
            "prompts.py": "def ask():\n    return input('pantry> ').strip()\n",
            "deeds.py": _PANTRY_DEEDS,
            "kitchen.py": (
                "import deeds\nfrom prompts import ask\n\n\n"
                "def main():\n"
                "    pantry = {'shelf': ['jam'], 'basket': []}\n"
                "    while True:\n"
                "        line = ask()\n"
                "        if line == 'peek':\n            print(deeds.peek(pantry))\n"
                "        elif line.startswith('fetch '):\n"
                "            print(deeds.fetch(pantry, line[6:]))\n"
                "        elif line == 'out':\n            break\n\n\n"
                "if __name__ == '__main__':\n    main()\n"
            ),
        },
    )
    cases = {
        "deeds.peek": [{"args": [_PANTRY]}],
        "deeds.fetch": [{"args": [_PANTRY, "jam"]}, {"args": [_PANTRY, "tea"]}],
        "kitchen.main": [
            {"args": [], "stdin": "peek\nfetch jam\nfetch tea\nout\n"},
        ],
    }

    outcome = _run_io(sub, cases, tmp_path)

    _assert_roles(outcome, {"roles": {"io": ["kitchen.main"], "logic": ["deeds"]}})
    assert outcome["status"] == "ok", outcome


def test_printing_action_that_changes_state_is_violated(tmp_path: Path) -> None:
    # glance only prints: user interface. grab prints and changes the
    # pantry: an action that prints instead of returning.
    sub = _write(
        tmp_path / "pantry",
        {
            "deeds.py": (
                "def glance(pantry):\n"
                "    print('On the shelf: ' + ', '.join(pantry['shelf']))\n\n\n"
                "def grab(pantry, thing):\n"
                "    if thing in pantry['shelf']:\n"
                "        pantry['shelf'].remove(thing)\n"
                "        pantry['basket'].append(thing)\n"
                "        print('Grabbed ' + thing + '.')\n"
                "    else:\n"
                "        print('No ' + thing + '.')\n"
            ),
            "kitchen.py": (
                "import deeds\n\n\n"
                "def main():\n"
                "    pantry = {'shelf': ['jam'], 'basket': []}\n"
                "    while True:\n"
                "        line = input('pantry> ')\n"
                "        if line == 'glance':\n            deeds.glance(pantry)\n"
                "        elif line.startswith('grab '):\n"
                "            deeds.grab(pantry, line[5:])\n"
                "        elif line == 'out':\n            break\n\n\n"
                "if __name__ == '__main__':\n    main()\n"
            ),
        },
    )
    cases = {
        "deeds.grab": [{"args": [_PANTRY, "jam"]}, {"args": [_PANTRY, "tea"]}],
        "kitchen.main": [{"args": [], "stdin": "glance\ngrab jam\nout\n"}],
    }
    prepared = global_tools.prepare_global_task(
        str(sub), "io_separation", cases, str(tmp_path / "task")
    )
    summary = global_tools.run_global_evaluation(
        str(sub), prepared["task_dirs"], str(tmp_path / "out"), sandbox="limits"
    )
    (outcome,) = summary["principles"]

    _assert_roles(outcome, {"roles": {"io": ["kitchen.main"], "logic": ["deeds.grab"]}})
    assert outcome["status"] == "violated", outcome
    assert {f["error_id"] for f in outcome["findings"]} == {"print_instead_of_return"}


def test_missing_call_in_every_case_is_unverified_not_violated(tmp_path: Path) -> None:
    # main computes the inventory itself and never calls deeds in any case:
    # in global mode whether it should depends on the discovered roles, so
    # the missing call is no proof.
    sub = _write(
        tmp_path / "pantry",
        {
            "deeds.py": _PANTRY_DEEDS,
            "kitchen.py": (
                "import deeds\n\n\n"
                "def main():\n"
                "    pantry = {'shelf': ['jam'], 'basket': []}\n"
                "    while True:\n"
                "        line = input('pantry> ')\n"
                "        if line == 'peek':\n"
                "            print('On the shelf: ' + ', '.join(pantry['shelf']))\n"
                "        elif line == 'fetch':\n"
                "            print(deeds.fetch(pantry, 'jam'))\n"
                "        elif line == 'out':\n            break\n\n\n"
                "if __name__ == '__main__':\n    main()\n"
            ),
        },
    )
    cases = {
        "deeds.peek": [{"args": [_PANTRY]}],
        "deeds.fetch": [{"args": [_PANTRY, "jam"]}, {"args": [_PANTRY, "tea"]}],
        "kitchen.main": [{"args": [], "stdin": "peek\nout\n"}],
    }

    outcome = _run_io(sub, cases, tmp_path)

    assert outcome["status"] == "unverified", outcome
    assert outcome["findings"] == []
    (missed,) = [u for u in outcome["unverified"] if u.get("entity") == "kitchen.main"]
    assert missed == {
        "entity": "kitchen.main",
        "reason": "missing_call_role_dependent",
        "error": "logic_in_main",
        "module": "deeds",
    }


_SHOP = {"shelf": ["bun", "loaf"], "sold": []}
_LOT = {"init": {"args": []}}
PRINTING_ACTION_CASES: dict[str, dict[str, list]] = {
    "bakery_l": {
        "oven.listing": [{"args": [_SHOP]}],
        "oven.sell": [{"args": [_SHOP, "bun"]}, {"args": [_SHOP, "cake"]}],
        "counter.main": [{"args": [], "stdin": "list\nsell bun\nsell cake\nclose\n"}],
    },
    "garage_m": {
        "cars.Lot.summary": [{**_LOT, "args": []}],
        "cars.Lot.fix": [{**_LOT, "args": ["van"]}, {**_LOT, "args": ["bike"]}],
        "workshop.Workshop.run": [
            {**_LOT, "args": [], "stdin": "lot\nfix van\nfix bike\ndone\n"}
        ],
    },
    "orchard_n": {
        "orchard.count": [{"args": []}],
        "orchard.pick": [{"args": ["apple"]}, {"args": ["plum"]}],
        "orchard.main": [{"args": [], "stdin": "count\npick apple\npick plum\nhome\n"}],
    },
}


@pytest.mark.parametrize("name", sorted(PRINTING_ACTION_CASES))
def test_printing_action_that_changes_state_is_found_in_every_scope(
    tmp_path: Path, name: str
) -> None:
    # An action that prints instead of returning and changes the game state:
    # through an alias (bakery_l), as a method of a model class (garage_m),
    # beside the game loop in one module (orchard_n). It is never an output
    # helper of the user interface.
    sub = FIXTURES / name
    expected = EXPECTED[name]["io_separation"]
    prepared = global_tools.prepare_global_task(
        str(sub), "io_separation", PRINTING_ACTION_CASES[name], str(tmp_path / "task")
    )
    assert prepared["problems"] == [] and prepared["dropped"] == [], prepared
    summary = global_tools.run_global_evaluation(
        str(sub), prepared["task_dirs"], str(tmp_path / "out"), sandbox="limits"
    )
    (outcome,) = summary["principles"]

    _assert_roles(outcome, expected)
    assert outcome["status"] == expected["status"], outcome
    assert {f["error_id"] for f in outcome["findings"]} == set(expected["errors"])


def test_global_tools_read_and_run_the_unchanged_submission_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit 2026-11-08 § 3: each tool call reads the submission's source
    once, and a judged principle runs the unchanged submission by its
    checks once (``run_evaluation``): the mutation check takes those results
    as its baseline instead of running a copy of it again."""
    import pythonarchtesting.runner as runner
    from pythonarchtesting.runner import source_prep

    sub = FIXTURES / "detective_b"
    scans: list[Path] = []
    runs: list[list[Path]] = []
    prepare_source, run_projects = source_prep.prepare_source, runner.run_projects

    def scanning(**kwargs: Any) -> Any:
        scans.append(Path(kwargs["source_path"]))
        return prepare_source(**kwargs)

    def running(*args: Any, **kwargs: Any) -> Any:
        runs.append([Path(t) for t in kwargs.get("targets") or []])
        return run_projects(*args, **kwargs)

    monkeypatch.setattr(source_prep, "prepare_source", scanning)
    monkeypatch.setattr(runner, "run_projects", running)

    prepared = global_tools.prepare_global_task(
        str(sub), "io_separation", DETECTIVE_B_IO_CASES, str(tmp_path / "task")
    )
    assert scans.count(sub) == 1
    scans.clear()
    summary = global_tools.run_global_evaluation(
        str(sub), prepared["task_dirs"], str(tmp_path / "out"), sandbox="limits"
    )

    assert [p["status"] for p in summary["principles"]] == ["ok"]
    assert scans.count(sub) == 1
    # The unchanged submission is the copy run_evaluation judges
    # (``target/<name>``); a mutant lives in a directory of its own id.
    unchanged = [
        t
        for targets in runs
        for t in targets
        if t.parent.name in ("target", "reference")
    ]
    assert len(unchanged) == 1 and unchanged[0].parent.name == "target", runs
    assert len(runs) == 2  # the evaluation, then the mutants alone
