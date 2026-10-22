"""Changes to an object's state that do not go through ``__setattr__``.

``forbid_foreign_writes`` sees ``obj.x = ...`` through the class's
``__setattr__``. A service can change an object just as well by changing what
an attribute holds (``order.items.append(x)``), by deleting an attribute, or
by writing past the class (``obj.__dict__[...]``, ``object.__setattr__``).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pythonarchtesting.dynamic.runner import run_cases

_MODELS = """
import random


class Account:
    def __init__(self):
        self.balance = 10
        self.history = []
        self.tags = {}

    def add(self, amount):
        self.history.append(amount)
        self.tags["last"] = amount
        self.balance += amount

    def forget(self):
        del self.balance

    def mix(self):
        random.shuffle(self.history)
        self.history[0] = self.history[-1]
"""

_SERVICE = """
import random

from .models import Account


def appends(account):
    account.history.append(1)


def sets_item(account):
    account.tags["a"] = 1


def replaces_item(account):
    account.history.append(1)
    account.history[0] = 2


def deletes(account):
    del account.balance


def through_dict(account):
    account.__dict__["balance"] = 0


def through_object(account):
    object.__setattr__(account, "balance", 0)


def direct(account):
    account.balance = 1


def through_methods(account):
    for amount in range(6):
        account.add(amount)
    account.mix()
    account.forget()


def reads(account):
    return len(account.history) + sum(account.history) + len(account.tags)


def shuffles(account):
    for amount in range(6):
        account.add(amount)
    random.shuffle(account.history)


def _store(history):
    history[0] = 7


def through_a_helper(account):
    account.add(1)
    _store(account.history)


def builds_and_appends():
    account = Account()
    account.history.append(1)
"""

_ACCOUNT = {"$new": "models.Account"}


@pytest.fixture(scope="module")
def root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    package = tmp_path_factory.mktemp("changes") / "bank_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "models.py").write_text(textwrap.dedent(_MODELS), encoding="utf-8")
    (package / "service.py").write_text(textwrap.dedent(_SERVICE), encoding="utf-8")
    return package


def _changes(root: Path, qualname: str, args: list | None = None) -> list[tuple]:
    outcome = run_cases(
        target_root=root,
        module_path="service",
        qualname=qualname,
        kind="function",
        cases=[{"args": [_ACCOUNT] if args is None else args}],
        init=None,
        timeout_s=10.0,
        observe={"writes": True},
    )
    assert outcome.status == "completed", (outcome.error, outcome.stderr)
    case = outcome.cases[0]
    assert "raised" not in case, case["raised"]
    return [
        (write["class"], write["attribute"], write.get("change", "assigned"))
        for write in case["writes"]
    ]


@pytest.mark.parametrize(
    ("qualname", "expected"),
    [
        ("appends", [("Account", "history", "mutated")]),
        ("sets_item", [("Account", "tags", "mutated")]),
        (
            "replaces_item",
            [("Account", "history", "mutated"), ("Account", "history", "mutated")],
        ),
        ("deletes", [("Account", "balance", "deleted")]),
        ("through_dict", [("Account", "balance", "bypassed")]),
        ("through_object", [("Account", "balance", "bypassed")]),
        ("direct", [("Account", "balance", "assigned")]),
        ("shuffles", [("Account", "history", "mutated")]),
        ("through_a_helper", [("Account", "history", "mutated")]),
    ],
)
def test_a_foreign_change_is_recorded_once_with_how_it_was_made(
    root: Path, qualname: str, expected: list[tuple]
) -> None:
    assert _changes(root, qualname) == expected


@pytest.mark.parametrize("qualname", ["through_methods", "reads"])
def test_changes_made_by_the_class_itself_or_mere_reads_are_not_recorded(
    root: Path, qualname: str
) -> None:
    assert _changes(root, qualname) == []


def test_an_object_built_while_the_case_runs_is_watched_too(root: Path) -> None:
    assert _changes(root, "builds_and_appends", args=[]) == [
        ("Account", "history", "mutated")
    ]


def test_the_change_names_the_line_that_made_it(root: Path) -> None:
    outcome = run_cases(
        target_root=root,
        module_path="service",
        qualname="appends",
        kind="function",
        cases=[{"args": [_ACCOUNT]}],
        init=None,
        timeout_s=10.0,
        observe={"writes": True},
    )
    (write,) = outcome.cases[0]["writes"]
    source = (root / "service.py").read_text(encoding="utf-8").splitlines()
    assert "account.history.append(1)" in source[write["line"] - 1]
    assert write["writer"] == "service:appends"


def test_a_change_inside_a_helper_names_the_helper(root: Path) -> None:
    outcome = run_cases(
        target_root=root,
        module_path="service",
        qualname="through_a_helper",
        kind="function",
        cases=[{"args": [_ACCOUNT]}],
        init=None,
        timeout_s=10.0,
        observe={"writes": True},
    )
    (write,) = outcome.cases[0]["writes"]
    assert write["writer"] == "service:_store"
