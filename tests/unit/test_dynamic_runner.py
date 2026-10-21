"""Tests for the child-interpreter runner behind the runtime structure markers."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pythonarchtesting.dynamic.runner import import_target_spec, run_cases

_SHOP = """
from __future__ import annotations

import pickle
import time

from . import repo

print("noise printed at import time")


class Item:
    def __init__(self, price: float, qty: int) -> None:
        self.price = price
        self.qty = qty


def total(items: list[Item]) -> float:
    print("noise printed while running")
    return sum(item.price * item.qty for item in items)


def save(store, key):
    return store.put(key, 1)


def _put(store):
    return store.put("k", 2)


def save_via_helper(store):
    return _put(store)


def _double(x):
    return x * 2


def local_only(values):
    return _double(len(values)) + max(values) + sorted(values)[0]


def dump(value):
    return pickle.dumps(value)


def parse(value: str) -> int:
    return int(value)


def spin() -> None:
    # Sleep rather than busy-loop: a spinning child would steal CPU from tests
    # running in parallel, such as the CLI start-up time budget.
    while True:
        time.sleep(0.1)


class Wallet:
    def __init__(self, balance: int = 0) -> None:
        if balance < 0:
            raise ValueError("negative opening balance")
        self.balance = balance

    def deposit(self, store) -> int:
        self.balance += 1
        store.put("balance", self.balance)
        return self.balance
"""

_REPO = """
class Store:
    def __init__(self):
        self.data = {}

    def put(self, key, value):
        self.data[key] = value
        return value
"""


@pytest.fixture
def package_root(tmp_path: Path) -> Path:
    root = tmp_path / "student_pkg"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "shop.py").write_text(textwrap.dedent(_SHOP), encoding="utf-8")
    (root / "repo.py").write_text(textwrap.dedent(_REPO), encoding="utf-8")
    return root


def _run(root: Path, qualname: str, kind: str, cases: list, **kwargs):
    return run_cases(
        target_root=root,
        module_path="shop",
        qualname=qualname,
        kind=kind,
        cases=cases,
        init=kwargs.get("init"),
        timeout_s=kwargs.get("timeout_s", 10.0),
        observe=kwargs.get("observe", {"calls": True}),
    )


def _line_of(fragment: str) -> int:
    lines = textwrap.dedent(_SHOP).splitlines()
    return next(no for no, line in enumerate(lines, 1) if fragment in line)


def _modules(case: dict) -> list[tuple[str, str]]:
    return [(call["module"], call["callee"]) for call in case["calls"]]


def test_import_target_spec_imports_a_package_root_by_name(package_root: Path):
    root, package = import_target_spec(package_root)

    assert root == package_root.resolve()
    assert package == "student_pkg"


def test_import_target_spec_puts_a_plain_root_on_the_path(tmp_path: Path):
    _, package = import_target_spec(tmp_path)

    assert package is None


def test_a_call_through_an_injected_object_is_attributed_to_its_module(
    package_root: Path,
):
    outcome = _run(
        package_root, "save", "function", [{"args": [{"$new": "repo.Store"}, "a"]}]
    )

    assert outcome.status == "completed"
    case = outcome.cases[0]
    assert case["status"] == "passed"
    # The package prefix is stripped; constructing the argument is not a call
    # the target made.
    assert case["calls"] == [
        {
            "from": "shop",
            "module": "repo",
            "callee": "Store.put",
            "caller": "save",
            "line": _line_of("return store.put(key, 1)"),
        }
    ]


def test_a_same_module_helper_is_followed_to_its_outward_call(package_root: Path):
    outcome = _run(
        package_root,
        "save_via_helper",
        "function",
        [{"args": [{"$new": "repo.Store"}]}],
    )

    calls = outcome.cases[0]["calls"]
    assert [(c["module"], c["callee"], c["caller"]) for c in calls] == [
        ("repo", "Store.put", "_put")
    ]


def test_same_module_helpers_and_builtins_are_not_reported(package_root: Path):
    outcome = _run(package_root, "local_only", "function", [{"args": [[3, 1, 2]]}])

    assert outcome.cases[0]["status"] == "passed"
    assert outcome.cases[0]["calls"] == []


def test_a_c_function_is_reported_under_its_public_module(package_root: Path):
    outcome = _run(package_root, "dump", "function", [{"args": [[1, 2]]}])

    assert _modules(outcome.cases[0]) == [("pickle", "dumps")]


def test_constructor_arguments_are_built_from_the_target(package_root: Path):
    outcome = _run(
        package_root,
        "total",
        "function",
        [
            {"args": [[]]},
            {
                "args": [
                    [
                        {"$new": "Item", "args": [0.1, 3]},
                        {"$new": "Item", "kwargs": {"price": 1.0, "qty": 2}},
                    ]
                ]
            },
        ],
    )

    assert outcome.status == "completed"
    assert [case["status"] for case in outcome.cases] == ["passed", "passed"]


def test_target_output_does_not_corrupt_the_response(package_root: Path):
    outcome = _run(package_root, "total", "function", [{"args": [[]]}])

    assert outcome.status == "completed"
    assert "noise printed at import time" in outcome.stderr
    assert "noise printed while running" in outcome.stderr


def test_an_exception_from_the_call_is_reported_not_judged(package_root: Path):
    outcome = _run(
        package_root, "parse", "function", [{"args": ["x"]}, {"args": ["7"]}]
    )

    raised, returned = outcome.cases
    assert raised["status"] == "passed"
    assert raised["failures"] == []
    assert raised["raised"].startswith("ValueError: invalid literal")
    assert "raised" not in returned


def test_system_exit_is_reported_and_does_not_end_the_probe(package_root: Path):
    (package_root / "shop.py").write_text(
        "import sys\n\ndef quit_now():\n    sys.exit(3)\n", encoding="utf-8"
    )

    outcome = _run(package_root, "quit_now", "function", [{}, {}])

    assert outcome.status == "completed"
    assert [case.get("raised") for case in outcome.cases] == [
        "SystemExit: 3",
        "SystemExit: 3",
    ]


def test_without_observe_nothing_is_recorded(package_root: Path):
    outcome = _run(
        package_root,
        "save",
        "function",
        [{"args": [{"$new": "repo.Store"}, "a"]}],
        observe=None,
    )

    assert outcome.cases[0]["status"] == "passed"
    assert "calls" not in outcome.cases[0]
    assert "writes" not in outcome.cases[0]


def test_method_cases_build_the_instance_with_the_shared_or_own_init(
    package_root: Path,
):
    outcome = _run(
        package_root,
        "Wallet.deposit",
        "method",
        [
            {"args": [{"$new": "repo.Store"}]},
            {"init": {"args": [-1]}, "args": [{"$new": "repo.Store"}]},
        ],
        init={"kwargs": {"balance": 10}},
    )

    shared, own = outcome.cases
    assert shared["status"] == "passed"
    assert _modules(shared) == [("repo", "Store.put")]
    assert shared["calls"][0]["caller"] == "Wallet.deposit"
    assert own["status"] == "error"
    assert "constructing 'Wallet' raised ValueError" in own["failures"][0]


def test_unresolvable_constructor_is_a_setup_error(package_root: Path):
    outcome = _run(
        package_root, "total", "function", [{"args": [[{"$new": "Missing"}]]}]
    )

    assert outcome.cases[0]["status"] == "error"
    assert "cannot resolve 'Missing'" in outcome.cases[0]["failures"][0]
    assert "calls" not in outcome.cases[0]


def test_static_and_class_methods_need_no_instance(package_root: Path):
    (package_root / "shop.py").write_text(
        textwrap.dedent("""
            import json


            class Needy:
                def __init__(self, required):
                    self.required = required

                @staticmethod
                def encode(x):
                    return json.dumps(x)

                @classmethod
                def name(cls):
                    return cls.__name__
            """),
        encoding="utf-8",
    )

    static = _run(package_root, "Needy.encode", "method", [{"args": [4]}])
    klass = _run(package_root, "Needy.name", "method", [{}])

    assert static.cases[0]["status"] == "passed"
    assert [c["module"] for c in static.cases[0]["calls"]] == ["json"]
    assert klass.cases[0]["status"] == "passed"


def test_timeout_keeps_what_the_target_wrote_to_stderr(package_root: Path):
    (package_root / "shop.py").write_text(
        "import sys\nimport time\n\ndef spin():\n"
        "    print('about to spin', file=sys.stderr, flush=True)\n"
        "    while True:\n        time.sleep(0.1)\n",
        encoding="utf-8",
    )

    outcome = _run(package_root, "spin", "function", [{}], timeout_s=2)

    assert outcome.status == "timeout"
    assert "about to spin" in outcome.stderr


def test_import_failure_is_reported_not_raised(package_root: Path):
    (package_root / "shop.py").write_text("raise RuntimeError('boom')\n")

    outcome = _run(package_root, "total", "function", [{}])

    assert outcome.status == "import_error"
    assert outcome.error == "RuntimeError: boom"
    assert outcome.cases == []


def test_a_target_that_never_returns_times_out(package_root: Path):
    outcome = _run(package_root, "spin", "function", [{}], timeout_s=1)

    assert outcome.status == "timeout"
    assert outcome.error == "target did not finish within 1 s"


def test_a_target_that_kills_the_interpreter_is_reported_as_crashed(
    package_root: Path,
):
    (package_root / "shop.py").write_text(
        "import os\n\ndef total(items):\n    os._exit(3)\n"
    )

    outcome = _run(package_root, "total", "function", [{"args": [[]]}])

    assert outcome.status == "crashed"
    assert "exited with code 3" in (outcome.error or "")
