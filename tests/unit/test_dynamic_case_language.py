"""Case values that set up a stateful or collaborating target.

``{"$spy": name, "returns": {...}}`` lets a stand-in answer a query, so the
code after it still runs; ``"steps"`` calls other methods of the same
instance before the observed call (or before a class's instance is
inspected), so behaviour that needs earlier calls can be reached. Neither
says what the target should compute.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pythonarchtesting.dynamic.runner import run_cases

_TARGET = """
from . import store


class Order:
    def label(self):
        return "order"


def show(repo, order_id):
    order = repo.find(order_id)
    return store.save(order.label())


class Cart:
    def __init__(self, audit):
        self.items = []
        self.audit = audit

    def add(self, item):
        self.audit.log(item)
        self.items.append(item)

    def checkout(self):
        return store.save(self.items[0])


class Account:
    def open(self):
        self.opened_at = 1

    def fail(self):
        raise ValueError("closed")
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    package = tmp_path / "cases_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "store.py").write_text(
        "def save(value):\n    return value\n", encoding="utf-8"
    )
    (package / "target.py").write_text(textwrap.dedent(_TARGET), encoding="utf-8")
    return package


def _run(root: Path, qualname: str, kind: str, case: dict, **observe):
    outcome = run_cases(
        target_root=root,
        module_path="target",
        qualname=qualname,
        kind=kind,
        cases=[case],
        init=None,
        timeout_s=10.0,
        observe=observe,
    )
    assert outcome.status == "completed", outcome.error
    return outcome.cases[0]


def test_a_spy_answers_a_query_with_the_value_it_was_given(root: Path) -> None:
    case = _run(
        root,
        "show",
        "function",
        {
            "args": [
                {"$spy": "repo", "returns": {"find": {"$new": "Order"}}},
                "A1",
            ]
        },
        calls=True,
    )

    assert case["status"] == "passed", case["failures"]
    assert "raised" not in case
    assert "store" in {call["module"] for call in case["calls"]}


def test_a_spy_without_returns_still_passes_its_first_argument_through(
    root: Path,
) -> None:
    case = _run(
        root, "show", "function", {"args": [{"$spy": "repo"}, "A1"]}, calls=True
    )

    # "A1".label() does not exist: the call stops there, as before.
    assert case["raised"].startswith("AttributeError")


def test_steps_prepare_the_instance_before_the_observed_call(root: Path) -> None:
    case = _run(
        root,
        "Cart.checkout",
        "method",
        {
            "init": {"args": [{"$spy": "audit"}]},
            "steps": [{"call": "add", "args": ["book"]}],
        },
        calls=True,
        spies=True,
    )

    assert case["status"] == "passed", case["failures"]
    assert "raised" not in case
    assert "store" in {call["module"] for call in case["calls"]}
    # What the steps did is preparation, not the observed behaviour.
    assert case["spy_calls"] == []


def test_steps_run_on_a_class_instance_before_its_members_are_read(
    root: Path,
) -> None:
    case = _run(
        root,
        "Account",
        "class",
        {"steps": [{"call": "open"}]},
        names=["opened_at"],
    )

    assert case["members"]["opened_at"]["present"] is True


def test_a_step_that_raises_means_the_case_could_not_be_set_up(root: Path) -> None:
    case = _run(
        root, "Account", "class", {"steps": [{"call": "fail"}]}, names=["opened_at"]
    )

    assert case["status"] == "error"
    assert case["failures"] == ["setup: step 0 (fail) raised ValueError: closed"]
