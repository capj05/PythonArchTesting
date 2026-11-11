"""How ``prepare_task`` picks the mutants of a typical error (no code runs)."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

import pytest

from pythonarchtesting.principles.task_mutants import (
    mutants_for,
    parameter_classes,
    seed_candidates,
)
from pythonarchtesting.principles.task_verification import _not_utf8, _run_mutants


def _error(operator: str, callee: Optional[str] = None) -> Any:
    return SimpleNamespace(
        id="e", operator=operator, signature=SimpleNamespace(callee=callee)
    )


def _mutant(operator: str, function: str, member: str, file: str = "app.py") -> Any:
    return SimpleNamespace(
        operator=operator, file=file, function=function, member=member
    )


def test_stub_role_call_keeps_only_calls_into_a_module_the_check_names() -> None:
    """``main`` also calls a project module the check does not name
    (``tools``) and a helper of its own module (``app``): those mutants are
    dropped, as is one in a function the check is not on."""
    mutants = [
        _mutant("stub_role_call", "main", "grades"),
        _mutant("stub_role_call", "main", "tools"),
        _mutant("stub_role_call", "main", "app"),
        _mutant("stub_role_call", "helper", "grades"),
        _mutant("add_io_call", "main", "print"),
    ]
    error = _error("stub_role_call")

    candidates = seed_candidates(error, mutants)
    chosen = mutants_for(error, candidates or [], {("app.py", "main")}, {"grades"})

    assert candidates == mutants[:4]
    assert chosen == [mutants[0]]


def test_an_io_operator_seeds_only_the_calls_it_can_make() -> None:
    mutants = [
        _mutant("add_io_call", "f", "print"),
        _mutant("add_io_call", "f", "input"),
        _mutant("add_io_via_helper", "f", "print"),
    ]

    assert seed_candidates(_error("add_io_call", "builtins:input"), mutants) == [
        mutants[1]
    ]
    assert seed_candidates(_error("add_io_via_helper", "builtins:print"), mutants) == [
        mutants[2]
    ]
    # The helper only prints: an error about input or open is not verifiable
    # by it, which is no ``no_mutants`` of the task.
    assert (
        seed_candidates(_error("add_io_via_helper", "builtins:input"), mutants) is None
    )
    assert seed_candidates(_error("add_io_via_helper", "io:open"), mutants) is None
    assert seed_candidates(_error("add_io_call", "os:system"), mutants) is None


def test_add_builtin_call_seeds_the_type_test_the_signature_names() -> None:
    mutants = [
        _mutant("add_builtin_call", "f", "print"),
        _mutant("add_builtin_call", "f", "isinstance"),
        _mutant("add_builtin_call", "f", "type"),
        _mutant("add_io_call", "f", "print"),
    ]

    assert seed_candidates(
        _error("add_builtin_call", "builtins:isinstance"), mutants
    ) == [mutants[1]]
    assert seed_candidates(_error("add_builtin_call", "builtins:type"), mutants) == [
        mutants[2]
    ]
    assert seed_candidates(_error("add_builtin_call", "builtins:print"), mutants) == [
        mutants[0]
    ]
    # The I/O-only alias cannot make a type test.
    assert (
        seed_candidates(_error("add_io_call", "builtins:isinstance"), mutants) is None
    )


def test_a_class_operator_is_aimed_at_the_classes_the_check_is_on() -> None:
    mutants = [
        _mutant("drop_base", "Circle", "Shape", "shapes.py"),
        _mutant("drop_base", "Shape", "ABC", "shapes.py"),
    ]
    error = _error("drop_base")

    chosen = mutants_for(
        error, seed_candidates(error, mutants) or [], {("shapes.py", "Circle")}, set()
    )

    assert chosen == [mutants[0]]


def test_a_constructor_operator_is_aimed_at_the_class_of_a_checked_method() -> None:
    """A method's cases build its object first, so a collaborator the
    constructor builds itself is seen by a check on any method of the class."""
    mutants = [
        _mutant("hardcode_collaborator", "Calc.__init__", "Half", "pricing.py"),
        _mutant("hardcode_collaborator", "Other.__init__", "Half", "pricing.py"),
        _mutant("hardcode_collaborator", "Calc.__init__", "Half", "other.py"),
        _mutant("add_io_call", "Calc.__init__", "print", "pricing.py"),
    ]
    aimed = {("pricing.py", "Calc.total")}

    error = _error("hardcode_collaborator")
    chosen = mutants_for(error, seed_candidates(error, mutants) or [], aimed, set())
    io_error = _error("add_io_call", "builtins:print")
    io_chosen = mutants_for(
        io_error, seed_candidates(io_error, mutants) or [], aimed, set()
    )

    assert chosen == [mutants[0]]
    # Only an injection operator reaches past the method into its constructor.
    assert io_chosen == []


def _entity(source: str, kind: str, qualname: str) -> Any:
    tree = ast.parse(source)
    node = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == qualname.split(".")[-1]
    )
    return SimpleNamespace(
        extras={"ast_node": node},
        kind=kind,
        filepath_rel="shop.py",
        qualname=qualname,
    )


def test_parameter_classes_come_from_the_cases_new_objects() -> None:
    source = (
        "class Shop:\n"
        "    def sell(self, stock, item, *, log=None):\n        pass\n\n\n"
        "def report(stock, title):\n    pass\n"
    )
    entities = {
        "m": _entity(source, "method", "Shop.sell"),
        "f": _entity(source, "function", "report"),
        "s": _entity(source, "function", "report"),
    }
    new = {"$new": "inventory.Inventory", "args": [{"a": 1}]}
    checks = [
        SimpleNamespace(
            entity_id="m",
            params={
                "cases": [{"args": [new, "a"], "kwargs": {"log": {"$new": "log.Log"}}}]
            },
        ),
        SimpleNamespace(entity_id="f", params={"cases": [{"args": [{"a": 1}, "x"]}]}),
        # A static check runs no cases and says nothing.
        SimpleNamespace(entity_id="s", params={"cases": None}),
    ]

    assert parameter_classes(checks, entities) == {
        ("shop.py", "Shop.sell"): {"stock": "Inventory", "log": "Log"},
        ("shop.py", "report"): {},
    }


def test_only_hardcode_collaborator_is_aimed_at_a_method_through_its_constructor() -> (
    None
):
    """A constructor mutant reaches the checks on the methods of its class;
    ``rebuild_injected`` names no function, so it never could (review of N5:
    the dead entry is gone, behaviour unchanged)."""
    from pythonarchtesting.principles.task_mutants import _in_aimed

    aimed = {("pricing.py", "Calc.total")}
    hardcoded = _mutant(
        "hardcode_collaborator", "Calc.__init__", "NoDiscount", "pricing.py"
    )
    rebuilt = SimpleNamespace(
        operator="rebuild_injected", file="pricing.py", function="", member=""
    )

    assert _in_aimed(hardcoded, aimed) is True
    assert _in_aimed(rebuilt, aimed) is False


def test_a_call_seeding_error_without_a_callee_seeds_the_calls_its_check_names() -> (
    None
):
    """type_switch_on_strategy names no callee: its mutants are the calls of
    isinstance and type its check forbids, not print or input."""
    from pythonarchtesting.principles.task_mutants import named_callees

    mutants = [
        _mutant("add_builtin_call", "f", member)
        for member in ("print", "input", "open", "isinstance", "type")
    ]
    error = _error("add_builtin_call")
    error.detected_by = "forbid_runtime_calls"
    checks = [
        SimpleNamespace(
            marker="forbid_runtime_calls",
            params={"modules": ["builtins.isinstance", "builtins.type"]},
        )
    ]

    callees = named_callees(error, checks)

    assert callees == ["builtins:isinstance", "builtins:type"]
    assert seed_candidates(error, mutants, callees) == mutants[3:]


def test_a_callee_less_error_names_the_callees_its_check_names() -> None:
    """Review of the N5 fix round: never 'cannot seed a call of None'."""
    from pythonarchtesting.principles.task_mutants import unseedable_reason

    error = _error("add_io_call")
    error.detected_by = "forbid_runtime_calls"
    checks = [
        SimpleNamespace(
            marker="forbid_runtime_calls", params={"modules": ["builtins.isinstance"]}
        )
    ]

    assert unseedable_reason(error, checks) == (
        "add_io_call cannot seed a call of any callee forbid_runtime_calls "
        "names (builtins:isinstance)"
    )
    named = _error("add_io_via_helper", "builtins:input")
    assert unseedable_reason(named, checks).endswith("a call of builtins:input")


def test_foreign_write_seeds_only_an_attribute_of_the_declared_privacy() -> None:
    """N7: replace_attribute is a write to a private attribute; a public one
    would be another error (killed_other), so it is no candidate."""
    mutants = [
        _mutant("foreign_write", "take", "items"),
        _mutant("foreign_write", "put", "_limit"),
    ]
    private = SimpleNamespace(
        id="e",
        operator="foreign_write",
        signature=SimpleNamespace(callee=None, private=True),
    )
    either = _error("foreign_write")

    assert seed_candidates(private, mutants) == [mutants[1]]
    assert seed_candidates(either, mutants) == mutants


def test_a_check_that_did_not_run_on_the_reference_is_a_problem() -> None:
    """Review of the N5 fix round: reference_fails always comes with its
    reason, also when the check did not run (a case that cannot be set up)."""
    from pythonarchtesting.principles.task_verification import _reference_problems

    rule = "DYN001/forbid_runtime_calls/v1"
    base = [
        SimpleNamespace(
            rule_id=rule,
            status="ERROR",
            message="",
            details={"reason": "reference_case_invalid", "summary": "case 0 ..."},
        ),
        SimpleNamespace(
            rule_id=rule, status="FAILED", message="", details={"summary": "calls x"}
        ),
        SimpleNamespace(rule_id=rule, status="OK", message="", details={}),
    ]

    assert _reference_problems(base, {"forbid_runtime_calls"}) == [
        "forbid_runtime_calls did not run on the reference "
        "(reference_case_invalid): case 0 ...",
        "forbid_runtime_calls fails on the reference: calls x",
    ]


def test_spied_follows_a_constructor_inherited_from_a_project_base() -> None:
    """Review of the N5 fix round: a context that inherits its constructor
    keeps the spy in the base's ``__init__``; both it and the mutants are
    aimed there."""
    from pythonarchtesting.principles.task_mutants import aimed_entities, spied

    source = (
        "class Base:\n    def __init__(self, discount):\n"
        "        self.discount = discount\n\n\n"
        "class Calc(Base):\n    def total(self, prices):\n"
        "        return self.discount.apply(sum(prices))\n"
    )
    tree = ast.parse(source)
    nodes = {
        name: next(
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name
        )
        for name in ("Base", "Calc", "__init__", "total")
    }
    entities = {
        key: SimpleNamespace(
            extras={"ast_node": nodes[node]},
            kind=kind,
            filepath_rel="pricing.py",
            qualname=qualname,
        )
        for key, kind, qualname, node in (
            ("b", "class", "Base", "Base"),
            ("c", "class", "Calc", "Calc"),
            ("i", "method", "Base.__init__", "__init__"),
            ("t", "method", "Calc.total", "total"),
        )
    }
    check = SimpleNamespace(
        entity_id="t",
        marker="require_runtime_delegation",
        not_applicable=None,
        params={"init": {"args": [{"$spy": "strategy"}]}},
    )
    error = SimpleNamespace(
        operator="hardcode_collaborator", detected_by="require_runtime_delegation"
    )

    assert spied([check], entities) == {("pricing.py", "Base"): {"discount"}}
    assert aimed_entities(error, [check], entities) == {
        ("pricing.py", "Calc.total"),
        ("pricing.py", "Base.__init__"),
    }


def test_max_mutants_takes_the_mutants_in_turn_from_each_error() -> None:
    """Audit K3: the mutants are taken in turn from each error (a mutant two
    errors share is taken once), not the first ``max_mutants`` by id, which
    left a whole error without any."""
    from pythonarchtesting.verification.mutant_runs import in_turn

    def mutants(*ids: str) -> list[Any]:
        return [SimpleNamespace(id=i) for i in ids]

    groups = [mutants("a1", "a2", "a3"), mutants("a1", "b2"), mutants("c1")]

    assert [m.id for m in in_turn(groups, 3)] == ["a1", "b2", "c1"]
    assert [m.id for m in in_turn(groups, 4)] == ["a1", "b2", "c1", "a2"]
    assert [m.id for m in in_turn(groups, 10)] == ["a1", "b2", "c1", "a2", "a3"]


def test_an_error_max_mutants_left_without_mutants_is_truncated() -> None:
    """Audit K3: an error whose mutants max_mutants dropped is ``truncated``,
    never ``no_mutants`` with "found nothing to change"."""
    from pythonarchtesting.principles.task_verification import _error_entry

    error = SimpleNamespace(
        id="e", detected_by="forbid_runtime_calls", operator="add_io_call"
    )

    entry = _error_entry(None, error, [], {}, dropped=4, max_mutants=2)

    assert entry["status"] == "truncated"
    assert entry["mutants"] == 0
    assert "max_mutants (2)" in entry["why"]
    assert _error_entry(None, error, [], {})["status"] == "no_mutants"


def _result(rule_id: str, status: str = "PASSED") -> Any:
    return SimpleNamespace(rule_id=rule_id, status=status, details={})


def _fake_run(monkeypatch: pytest.MonkeyPatch, status: str) -> list[list[str]]:
    """``run_projects`` gives every target a result of each marker with
    ``status``; the targets of each call are recorded."""
    import pythonarchtesting.runner as runner

    calls: list[list[str]] = []

    def run_projects(*, targets: list[str], rule_filter: Any, **_: Any) -> Any:
        calls.append(list(targets))
        rules = [SimpleNamespace(rule_id=f"R{i}/{m}/v1") for i, m in enumerate("ab")]
        kept = [r for r in rules if rule_filter(r)]
        states = [
            SimpleNamespace(
                target_path=target,
                rule_results=[_result(r.rule_id, status) for r in kept],
            )
            for target in targets
        ]
        return None, states

    monkeypatch.setattr(runner, "run_projects", run_projects)
    return calls


def _task(tmp_path: Path) -> Any:
    reference = tmp_path / "task" / "reference"
    reference.mkdir(parents=True)
    (reference / "app.py").write_text("x = 1\n", encoding="utf-8")
    return SimpleNamespace(reference=reference, path=tmp_path / "task")


def test_a_supplied_baseline_with_every_marker_does_not_run_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _fake_run(monkeypatch, "FAILED")
    given = [_result("R0/a/v1"), _result("R1/b/v1")]

    base, results = _run_mutants(_task(tmp_path), None, [], {"a", "b"}, None, given)

    assert calls == []
    assert base == given and results == {}


def test_a_marker_missing_from_the_supplied_baseline_runs_on_the_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _fake_run(monkeypatch, "FAILED")
    given = [_result("R0/a/v1")]

    base, results = _run_mutants(_task(tmp_path), None, [], {"a", "b"}, None, given)

    assert len(calls) == 1 and len(calls[0]) == 1
    assert [(r.rule_id, r.status) for r in base] == [
        ("R0/a/v1", "PASSED"),
        ("R1/b/v1", "FAILED"),
    ]
    assert results == {}


def test_only_a_required_marker_missing_from_the_baseline_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A marker the task has no check of (no rule to run) does not make the
    unchanged reference run again."""
    calls = _fake_run(monkeypatch, "FAILED")
    given = [_result("R0/a/v1")]

    base, _ = _run_mutants(
        _task(tmp_path), None, [], {"a", "b"}, None, given, required={"a"}
    )

    assert calls == [] and base == given


def test_not_utf8_does_not_look_into_a_virtual_environment(tmp_path: Path) -> None:
    (tmp_path / "reference").mkdir()
    (tmp_path / "reference" / "app.py").write_bytes(b"x = '\xe9'\n")
    for skipped in ("venv", ".venv", "__pycache__", ".hidden"):
        (tmp_path / skipped).mkdir()
        (tmp_path / skipped / "lib.py").write_bytes(b"y = '\xe9'\n")
    error = UnicodeDecodeError("utf-8", b"\xe9", 0, 1, "invalid continuation byte")

    message = _not_utf8(tmp_path, error)

    assert message.startswith("reference/app.py is not UTF-8")
    assert "venv" not in message and "hidden" not in message
