"""In-process tests for the probe's class inspection (DYN005-DYN007).

The classes live in a throwaway module built under ``tmp_path``; the probe is
asked what an instance looks like, never what it computes.
"""

from __future__ import annotations

import sys
import textwrap
import types
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.dynamic import probe

_SOURCE = """
from collections.abc import Sized


class Base:
    shared = "base"

    def greet(self, who):
        return who


class Settings(Base):
    kind = "settings"

    def __init__(self, port=1, fail=False):
        if fail:
            raise ValueError("bad port")
        self.port = port

    @property
    def broken(self):
        raise RuntimeError("no value yet")

    def __getattr__(self, name):
        if name == "lazy":
            return 42
        raise AttributeError(name)

    def export(self, rows, header=None):
        return rows

    def strict(self, rows, *, sep):
        return rows

    def tight(self):
        return None

    fetch = staticmethod(getattr)


class Slotted:
    __slots__ = ("host", "port")

    def __init__(self):
        self.host = "h"


class Sizeless(Sized):
    pass


NOT_A_CLASS = 3
"""


@pytest.fixture
def module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    filename = tmp_path / "shapes.py"
    module = types.ModuleType("shapes")
    module.__file__ = str(filename)
    monkeypatch.setitem(sys.modules, "shapes", module)
    exec(  # nosec B102
        compile(textwrap.dedent(_SOURCE), str(filename), "exec"), module.__dict__
    )
    return module


def _inspect(
    module: types.ModuleType,
    qualname: str,
    case: dict[str, Any] | None = None,
    **observe: Any,
) -> dict[str, Any]:
    request = {"qualname": qualname, "kind": "class", "observe": observe}
    return probe._run_case(0, case or {}, request, module, None)


def test_members_report_where_they_come_from(module: types.ModuleType) -> None:
    outcome = _inspect(
        module,
        "Settings",
        names=["port", "kind", "shared", "greet", "lazy", "missing"],
    )

    assert outcome["status"] == "passed"
    assert outcome["constructed"] is True
    assert outcome["abstract"] is False
    assert outcome["abstract_methods"] == []
    members = outcome["members"]
    assert members["port"] == {"present": True, "where": "instance"}
    assert members["kind"] == {"present": True, "where": "shapes.Settings"}
    assert members["shared"] == {"present": True, "where": "shapes.Base"}
    assert members["greet"] == {"present": True, "where": "shapes.Base"}
    assert members["lazy"] == {"present": True, "where": "dynamic"}
    assert members["missing"] == {"present": False}


def test_a_raising_property_is_present_but_not_callable(
    module: types.ModuleType,
) -> None:
    member = probe._describe_member(module.Settings(), "broken", None)
    assert member == {"present": True, "where": "shapes.Settings"}

    with_arity = probe._describe_member(module.Settings(), "broken", 0)
    assert with_arity["callable"] is False
    assert with_arity["error"] == "RuntimeError: no value yet"


def test_an_unset_slot_is_missing_and_a_set_one_is_on_the_instance(
    module: types.ModuleType,
) -> None:
    outcome = _inspect(module, "Slotted", names=["host", "port"])

    assert outcome["members"] == {
        "host": {"present": True, "where": "instance"},
        "port": {"present": False},
    }


@pytest.mark.parametrize(
    ("name", "arity", "bindable"),
    [
        ("export", 1, True),
        ("export", 2, True),
        ("export", 0, False),
        ("export", 3, False),
        ("tight", 1, False),
        ("strict", 1, True),
        ("greet", 1, True),
        ("fetch", 2, True),
    ],
)
def test_callables_are_checked_for_their_positional_arity(
    module: types.ModuleType, name: str, arity: int, bindable: bool
) -> None:
    outcome = _inspect(module, "Settings", callables={name: arity})

    member = outcome["members"][name]
    assert member["present"] is True
    assert member["callable"] is True
    assert member["bindable"] is bindable


def test_a_non_callable_member_is_reported_as_such(module: types.ModuleType) -> None:
    member = probe._describe_member(module.Settings(), "kind", 1)

    assert member["callable"] is False
    assert "bindable" not in member


def test_construct_false_only_reports_abstractness(module: types.ModuleType) -> None:
    outcome = _inspect(module, "Settings", construct=False, names=["port"])

    assert outcome["abstract"] is False
    assert "constructed" not in outcome
    assert "members" not in outcome


def test_a_raising_constructor_is_reported_not_judged(
    module: types.ModuleType,
) -> None:
    outcome = _inspect(module, "Settings", {"kwargs": {"fail": True}}, names=["port"])

    assert outcome["status"] == "passed"
    assert outcome["constructed"] is False
    assert outcome["raised"] == "ValueError: bad port"
    assert "members" not in outcome


def test_case_arguments_reach_the_constructor(module: types.ModuleType) -> None:
    outcome = _inspect(module, "Settings", {"args": [8080]}, names=["port"])

    assert outcome["constructed"] is True
    assert outcome["members"]["port"]["present"] is True


def test_abstractness_comes_from_a_standard_library_base(
    module: types.ModuleType,
) -> None:
    outcome = _inspect(module, "Sizeless")

    assert outcome["abstract"] is True
    assert outcome["abstract_methods"] == ["__len__"]
    assert outcome["constructed"] is False
    assert outcome["raised"].startswith("TypeError")


@pytest.mark.parametrize(
    ("qualname", "case", "fragment"),
    [
        ("NOT_A_CLASS", {}, "'NOT_A_CLASS' is not a class"),
        ("Nowhere", {}, "cannot resolve 'Nowhere'"),
        ("Settings", {"args": [{"$new": "Nowhere"}]}, "cannot resolve 'Nowhere'"),
    ],
)
def test_a_target_that_cannot_be_set_up_is_an_error(
    module: types.ModuleType, qualname: str, case: dict, fragment: str
) -> None:
    outcome = _inspect(module, qualname, case)

    assert outcome["status"] == "error"
    assert len(outcome["failures"]) == 1
    assert outcome["failures"][0].startswith("setup: ")
    assert fragment in outcome["failures"][0]
    assert "abstract" not in outcome


def test_accepts_positional_gives_an_unintrospectable_callable_the_benefit() -> None:
    assert probe._accepts_positional(max, 2) is True
    assert probe._accepts_positional(lambda a, b: None, 1) is False
    assert probe._accepts_positional(lambda a, *, b: None, 1) is True
