"""``write_self_task``: a submission written as its own reference."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from pythonarchtesting.global_mode.model import (
    BoundEntity,
    PrincipleOutcome,
    RoleDiscovery,
)
from pythonarchtesting.global_mode.selftask import SelfTask, _toml, write_self_task
from pythonarchtesting.principles.catalog import UnknownPrincipleError

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "global_mode"
_SHIP = {"$new": "ship.State"}
_CASE = {"$new": "case.State"}
# Every function of space_a.actions except take.
_SPACE_A_CASES = {
    "actions.load": [{"args": [_SHIP, ["load", "crate"]]}],
    "actions.total_power": [{"args": [[{"$new": "ship.Reactor"}]]}],
    "actions.status": [{"args": [_SHIP, ["status"]]}],
    "actions.go": [{"args": [_SHIP, ["go", "lab"]]}],
    "ui.main": [{"args": [], "stdin": "status\nkonec\n"}],
}


def _read(task: SelfTask) -> dict:
    return tomllib.loads((task.task_dir / "task.toml").read_text(encoding="utf-8"))


def test_entity_without_cases_is_dropped_not_lost(tmp_path: Path) -> None:
    task = write_self_task(
        FIXTURES / "space_a",
        "io_separation",
        roles={"logic": ["actions"], "io": ["ui.main"]},
        cases=_SPACE_A_CASES,
        out_dir=tmp_path / "task",
    )

    assert task.dropped == (
        {"entity": "actions.take", "role": "logic", "reason": "no cases"},
    )
    # The module is replaced by its functions that have cases, in the order
    # of the core's entities.
    assert _read(task)["roles"] == {
        "logic": [
            "actions.go",
            "actions.load",
            "actions.status",
            "actions.total_power",
        ],
        "io": ["ui.main"],
    }
    assert SelfTask.load(task.task_dir) == task


def test_module_with_all_cases_stays_bound_as_module(tmp_path: Path) -> None:
    cases = {**_SPACE_A_CASES, "actions.take": [{"args": [_SHIP, ["take"]]}]}

    task = write_self_task(
        FIXTURES / "space_a",
        "io_separation",
        roles={"logic": ["actions"], "io": ["ui.main"]},
        cases=cases,
        out_dir=tmp_path / "task",
    )

    assert task.dropped == ()
    assert _read(task)["roles"]["logic"] == ["actions"]
    assert _read(task)["cases"] == cases


def test_role_left_empty_is_not_written(tmp_path: Path) -> None:
    task = write_self_task(
        FIXTURES / "space_a",
        "io_separation",
        roles={"logic": ["actions.take"], "io": ["ui.main"]},
        cases={"ui.main": [{"args": [], "stdin": "konec\n"}]},
        out_dir=tmp_path / "task",
    )

    assert task.dropped == (
        {"entity": "actions.take", "role": "logic", "reason": "no cases"},
    )
    assert _read(task)["roles"] == {"io": ["ui.main"]}


def test_static_only_role_needs_no_cases(tmp_path: Path) -> None:
    task = write_self_task(
        FIXTURES / "space_a",
        "polymorphism",
        roles={"base": ["ship.Module"], "variant": ["ship.Reactor", "ship.SolarPanel"]},
        cases={},
        out_dir=tmp_path / "task",
    )

    assert task.dropped == ()
    data = _read(task)
    assert data["roles"] == {
        "base": ["ship.Module"],
        "variant": ["ship.Reactor", "ship.SolarPanel"],
    }
    assert "cases" not in data


def test_reference_is_absolute_path_of_submission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(FIXTURES)

    task = write_self_task(
        Path("space_a"),
        "polymorphism",
        roles={"base": ["ship.Module"]},
        cases={},
        out_dir=tmp_path / "task",
    )

    reference = _read(task)["reference"]
    assert Path(reference).is_absolute()
    assert reference == str((FIXTURES / "space_a").resolve())


def test_init_and_awkward_values_survive_the_round_trip(tmp_path: Path) -> None:
    cases = {
        "ship.Cargo.load": [
            {"args": ['a "quoted"\\ crate\n', 1.5, -2, True, [], {}]},
            {"args": ["čeština \x7f\t", 1e-05, False, [{"$new": "ship.Reactor"}]]},
        ]
    }

    task = write_self_task(
        FIXTURES / "space_a",
        "encapsulation",
        roles={"owner": ["ship.Cargo"], "client": ["ship.Cargo.load"]},
        cases=cases,
        out_dir=tmp_path / "task",
        init={"ship.Cargo.load": {"args": [2]}},
    )

    data = _read(task)
    assert data["cases"] == cases
    assert data["init"] == {"ship.Cargo.load": {"args": [2]}}


def test_toml_refuses_what_it_cannot_write() -> None:
    with pytest.raises(TypeError):
        _toml(None)
    assert _toml(float("inf")) == "inf"
    assert _toml(float("-inf")) == "-inf"
    assert _toml(float("nan")) == "nan"


def test_unknown_principle_is_refused(tmp_path: Path) -> None:
    with pytest.raises(UnknownPrincipleError):
        write_self_task(
            FIXTURES / "space_a", "no_such", roles={}, cases={}, out_dir=tmp_path
        )


def test_detective_b_with_absolute_imports_runs(tmp_path: Path) -> None:
    """Review focus 5: ``console.py`` imports ``from case import State``; the
    self-task runs it as ``run_evaluation`` runs a package today."""
    from pythonarchtesting.mcp_server.evaluation import run_evaluation
    from pythonarchtesting.mcp_server.reports import load_report

    task = write_self_task(
        FIXTURES / "detective_b",
        "io_separation",
        roles={"logic": ["commands"], "io": ["console.run"]},
        cases={
            "commands.search": [{"args": [_CASE, ["search", "knife"]]}],
            "commands.walk": [{"args": [_CASE, ["walk", "hall"]]}],
            "commands.notes": [{"args": [_CASE, ["notes"]]}],
            "console.run": [{"args": [], "stdin": "search knife\nnotes\nkonec\n"}],
        },
        out_dir=tmp_path / "task",
    )
    copy = tmp_path / "target" / "detective_b"
    shutil.copytree(FIXTURES / "detective_b", copy)

    run = run_evaluation(
        str(task.task_dir),
        str(tmp_path / "out"),
        targets=[str(copy)],
        dynamic=True,
        sandbox="limits",
    )

    (target,) = load_report(run["report_json"])["targets"]
    assert target["summary"]["results_total"] == 4, target["summary"]
    assert {r["status"] for r in target["results"]} == {"OK"}, target["results"]


def test_model_to_dict() -> None:
    owner = BoundEntity("ship.Cargo", "code", "list _crates in __init__")
    doubted = BoundEntity("ship.State", "ai", "holds the game", disputed="a helper")
    discovery = RoleDiscovery(
        "encapsulation", {"owner": (owner, doubted)}, ("ship.State",), None
    )
    outcome = PrincipleOutcome(
        principle="encapsulation",
        status="violated",
        roles={"owner": (owner,)},
        findings=({"error": "bypass_method", "line": 3},),
        unverified=(),
        coverage=None,
        mutation=None,
        sites=5,
        violations=1,
    )

    assert discovery.to_dict() == {
        "principle": "encapsulation",
        "roles": {
            "owner": [
                {
                    "entity": "ship.Cargo",
                    "source": "code",
                    "why": "list _crates in __init__",
                },
                {
                    "entity": "ship.State",
                    "source": "ai",
                    "why": "holds the game",
                    "disputed": "a helper",
                },
            ]
        },
        "conflicts": ["ship.State"],
        "not_applied": None,
    }
    data = outcome.to_dict()
    assert (data["sites"], data["ok"], data["violations"]) == (5, 4, 1)
    assert data["findings"] == [{"error": "bypass_method", "line": 3}]
    assert data["mutation"] is None and data["coverage"] is None


_HIDDEN_LOGIC = (
    "def a(x):\n    return x + 1\n\n"
    "if True:\n\n    def b(x):\n        return x * 2\n"
)
_UI = "import logic\n\n\ndef main():\n    print(logic.a(int(input())))\n"


def _hidden_submission(root: Path, extra: str = "") -> Path:
    """A module whose ``b`` sits under a module-level ``if``: the core's
    extraction counts it as a top-level public function."""
    sub = root / "sub"
    sub.mkdir(parents=True)
    (sub / "logic.py").write_text(_HIDDEN_LOGIC + extra, encoding="utf-8")
    (sub / "ui.py").write_text(_UI, encoding="utf-8")
    return sub


def _binds(task: SelfTask) -> None:
    """The written task binds to its reference as ``prepare_task`` binds it."""
    from pythonarchtesting.mcp_server.evaluation import resolve_config
    from pythonarchtesting.principles.task import bind_task, load_task
    from pythonarchtesting.runner.source_prep import prepare_source

    loaded = load_task(task.task_dir)
    config, _ = resolve_config(loaded.reference, None)
    entities = prepare_source(config=config, source_path=loaded.reference)
    bind_task(loaded, entities.source_entities)


_UI_CASES = {"ui.main": [{"args": [], "stdin": "3\n"}]}


def test_hidden_def_without_cases_is_dropped_not_bound_as_module(
    tmp_path: Path,
) -> None:
    sub = _hidden_submission(tmp_path)

    task = write_self_task(
        sub,
        "io_separation",
        roles={"logic": ["logic"], "io": ["ui.main"]},
        cases={"logic.a": [{"args": [1]}], **_UI_CASES},
        out_dir=tmp_path / "t",
    )

    assert task.dropped == (
        {"entity": "logic.b", "role": "logic", "reason": "no cases"},
    )
    assert _read(task)["roles"]["logic"] == ["logic.a"]
    _binds(task)


def test_hidden_def_is_dropped_when_the_module_is_replaced(tmp_path: Path) -> None:
    sub = _hidden_submission(tmp_path, "\n\ndef c(x):\n    return -x\n")

    task = write_self_task(
        sub,
        "io_separation",
        roles={"logic": ["logic"], "io": ["ui.main"]},
        cases={"logic.a": [{"args": [1]}], **_UI_CASES},
        out_dir=tmp_path / "t",
    )

    assert sorted(d["entity"] for d in task.dropped) == ["logic.b", "logic.c"]
    assert _read(task)["roles"]["logic"] == ["logic.a"]
    _binds(task)


def test_hidden_def_with_cases_keeps_the_module_whole(tmp_path: Path) -> None:
    sub = _hidden_submission(tmp_path)

    task = write_self_task(
        sub,
        "io_separation",
        roles={"logic": ["logic"], "io": ["ui.main"]},
        cases={"logic.a": [{"args": [1]}], "logic.b": [{"args": [2]}], **_UI_CASES},
        out_dir=tmp_path / "t",
    )

    assert task.dropped == ()
    assert _read(task)["roles"]["logic"] == ["logic"]
    _binds(task)
