"""How ``prepare_task`` picks the mutants of a typical error (no code runs)."""

from __future__ import annotations

import ast
from types import SimpleNamespace
from typing import Any, Optional

from pythonarchtesting.mcp_server.tasks import (
    _candidates,
    _mutants_for,
    parameter_classes,
)


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

    candidates = _candidates(error, mutants)
    chosen = _mutants_for(error, candidates or [], {("app.py", "main")}, {"grades"})

    assert candidates == mutants[:4]
    assert chosen == [mutants[0]]


def test_an_io_operator_seeds_only_the_calls_it_can_make() -> None:
    mutants = [
        _mutant("add_io_call", "f", "print"),
        _mutant("add_io_call", "f", "input"),
        _mutant("add_io_via_helper", "f", "print"),
    ]

    assert _candidates(_error("add_io_call", "builtins:input"), mutants) == [mutants[1]]
    assert _candidates(_error("add_io_via_helper", "builtins:print"), mutants) == [
        mutants[2]
    ]
    # The helper only prints: an error about input or open is not verifiable
    # by it, which is no ``no_mutants`` of the task.
    assert _candidates(_error("add_io_via_helper", "builtins:input"), mutants) is None
    assert _candidates(_error("add_io_via_helper", "io:open"), mutants) is None
    assert _candidates(_error("add_io_call", "os:system"), mutants) is None


def test_add_builtin_call_seeds_the_type_test_the_signature_names() -> None:
    mutants = [
        _mutant("add_builtin_call", "f", "print"),
        _mutant("add_builtin_call", "f", "isinstance"),
        _mutant("add_builtin_call", "f", "type"),
        _mutant("add_io_call", "f", "print"),
    ]

    assert _candidates(_error("add_builtin_call", "builtins:isinstance"), mutants) == [
        mutants[1]
    ]
    assert _candidates(_error("add_builtin_call", "builtins:type"), mutants) == [
        mutants[2]
    ]
    assert _candidates(_error("add_builtin_call", "builtins:print"), mutants) == [
        mutants[0]
    ]
    # The I/O-only alias cannot make a type test.
    assert _candidates(_error("add_io_call", "builtins:isinstance"), mutants) is None


def test_a_class_operator_is_aimed_at_the_classes_the_check_is_on() -> None:
    mutants = [
        _mutant("drop_base", "Circle", "Shape", "shapes.py"),
        _mutant("drop_base", "Shape", "ABC", "shapes.py"),
    ]
    error = _error("drop_base")

    chosen = _mutants_for(
        error, _candidates(error, mutants) or [], {("shapes.py", "Circle")}, set()
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
    chosen = _mutants_for(error, _candidates(error, mutants) or [], aimed, set())
    io_error = _error("add_io_call", "builtins:print")
    io_chosen = _mutants_for(
        io_error, _candidates(io_error, mutants) or [], aimed, set()
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
    from pythonarchtesting.mcp_server.tasks import _in_aimed

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
    from pythonarchtesting.mcp_server.tasks import _callees

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

    callees = _callees(error, checks)

    assert callees == ["builtins:isinstance", "builtins:type"]
    assert _candidates(error, mutants, callees) == mutants[3:]
