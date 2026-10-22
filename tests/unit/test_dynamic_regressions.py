"""Regression tests for probe defects found by running real targets.

Each test runs a throwaway package under ``tmp_path`` through the public
runner API, so the probe runs in a child interpreter exactly as in a
``--dynamic`` run.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from pythonarchtesting.dynamic.runner import run_case_batch, run_cases
from pythonarchtesting.runner.skips import (
    count_runtime_results_unverified,
    count_runtime_rules_skipped,
)

_TARGET = """
import collections
import os
import sys
import threading
import time

from . import helper


def slow():
    time.sleep(1.2)


def paths():
    Pair = collections.namedtuple("Pair", "left right")
    pair = Pair(os.path.join("a", "b"), "c")
    return helper.size(pair)


def leave_a_thread_running():
    threading.Thread(target=_forever).start()
    return 1


def _forever():
    while True:
        time.sleep(0.05)


class BadError(Exception):
    def __str__(self):
        raise RuntimeError("no text for you")


class NonStringError(Exception):
    def __str__(self):
        return 42


def raise_unprintable():
    raise BadError()


def raise_non_string():
    raise NonStringError()


def close_stdout():
    sys.stdout.close()
    return 1


def noop():
    return 1
"""

_HELPER = """
def size(value):
    return len(value)
"""

_WRITES = """
class Base:
    pass


class Validated(Base):
    def __init__(self):
        self.x = 1

    def __setattr__(self, name, value):
        if name.startswith("_"):
            raise AttributeError(name)
        super().__setattr__(name, value)


def _checked_setattr(self, name, value):
    # Defined outside the class, so only __wrapped__ ties it to Checked.
    if name.startswith("_"):
        raise AttributeError(name)
    Base.__setattr__(self, name, value)


class Checked(Base):
    __setattr__ = _checked_setattr

    def __init__(self):
        self.y = 1


def logged(function):
    # No functools.wraps: the class dictionary holds ``inner``, not ``set``.
    def inner(self, *args):
        return function(self, *args)

    return inner


class Account:
    def __init__(self):
        self.v = 0

    @logged
    def set(self, value):
        self.v = value

    def via_helper(self):
        def helper(target):
            target.v = 2

        helper(self)


def build_validated():
    return Validated().x


def build_checked():
    return Checked().y


def set_through_decorator():
    account = Account()
    account.set(3)
    return account.v


def set_through_nested_helper():
    Account().via_helper()


def poke(account):
    account.v = 4
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    package = tmp_path / "regress_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "target.py").write_text(textwrap.dedent(_TARGET), encoding="utf-8")
    (package / "helper.py").write_text(textwrap.dedent(_HELPER), encoding="utf-8")
    (package / "writes.py").write_text(textwrap.dedent(_WRITES), encoding="utf-8")
    return package


def _job(job_id: str, qualname: str, timeout_s: float = 5.0, **observe) -> dict:
    return {
        "id": job_id,
        "qualname": qualname,
        "kind": "function",
        "cases": [{}],
        "init": None,
        "timeout_s": timeout_s,
        "observe": observe,
    }


def _run(root: Path, qualname: str, timeout_s: float = 10.0, **observe):
    return run_cases(
        target_root=root,
        module_path="target",
        qualname=qualname,
        kind="function",
        cases=[{}],
        init=None,
        timeout_s=timeout_s,
        observe=observe,
    )


def test_a_batch_job_is_not_charged_the_time_of_earlier_jobs(root: Path) -> None:
    # 3 x 1.2 s exceeds every job's 2 s; each job alone stays within it.
    outcome = run_case_batch(
        target_root=root,
        module_path="target",
        jobs=[_job(str(i), "slow", timeout_s=2.0) for i in range(3)],
    )

    assert outcome.status == "completed"
    assert {key: job["status"] for key, job in outcome.jobs.items()} == {
        "0": "completed",
        "1": "completed",
        "2": "completed",
    }


def test_edges_skip_frozen_and_generated_code(root: Path) -> None:
    outcome = _run(root, "paths", calls="edges")

    assert outcome.status == "completed"
    case = outcome.cases[0]
    assert case["status"] == "passed", case["failures"]
    # "<frozen posixpath>" and the namedtuple's "<string>" code once passed
    # for project files, since relative names resolve against the root.
    assert [(c["from"], c["module"], c["callee"]) for c in case["calls"]] == [
        ("target", "helper", "size")
    ]


def test_a_thread_left_running_does_not_turn_the_run_into_a_timeout(
    root: Path,
) -> None:
    outcome = _run(root, "leave_a_thread_running", timeout_s=3.0)

    assert outcome.status == "completed"
    assert [case["status"] for case in outcome.cases] == ["passed"]


@pytest.mark.parametrize(
    ("qualname", "expected"),
    [
        ("raise_unprintable", "BadError: <unprintable>"),
        ("raise_non_string", "NonStringError: <unprintable>"),
    ],
)
def test_an_exception_that_cannot_be_printed_is_still_reported(
    root: Path, qualname: str, expected: str
) -> None:
    outcome = _run(root, qualname)

    assert outcome.status == "completed"
    assert outcome.cases[0]["raised"] == expected


def test_target_closing_stdout_does_not_break_the_batch(root: Path) -> None:
    outcome = run_case_batch(
        target_root=root,
        module_path="target",
        jobs=[_job("0", "close_stdout"), _job("1", "noop")],
    )

    assert outcome.status == "completed"
    assert {key: job["status"] for key, job in outcome.jobs.items()} == {
        "0": "completed",
        "1": "completed",
    }


def _writes(root: Path, *jobs: dict) -> dict[str, list[tuple[str, str]]]:
    outcome = run_case_batch(target_root=root, module_path="writes", jobs=list(jobs))
    assert outcome.status == "completed"
    return {
        key: [(w["attribute"], w["writer"]) for w in job["cases"][0]["writes"]]
        for key, job in outcome.jobs.items()
    }


def test_an_own_setattr_that_calls_super_is_not_a_foreign_write(root: Path) -> None:
    # Base's wrapper sees the subclass's original __setattr__ as the writer;
    # the class dictionary now holds the wrapper, which names it in
    # __wrapped__. Checked's is a module function, so its qualified name does
    # not place it in the class.
    assert _writes(
        root,
        _job("0", "build_validated", writes=True),
        _job("1", "build_checked", writes=True),
    ) == {"0": [], "1": []}


@pytest.mark.skipif(sys.version_info < (3, 11), reason="needs co_qualname")
def test_a_method_behind_a_decorator_without_wraps_owns_its_writes(
    root: Path,
) -> None:
    assert _writes(root, _job("0", "set_through_decorator", writes=True)) == {"0": []}


def test_nested_helpers_and_module_functions_still_write_foreign(
    root: Path,
) -> None:
    writes = _writes(
        root,
        _job("0", "set_through_nested_helper", writes=True),
        {
            **_job("1", "poke", writes=True),
            "cases": [{"args": [{"$new": "Account"}]}],
        },
    )

    nested = "Account.via_helper.<locals>.helper"
    if sys.version_info < (3, 11):
        nested = "helper"
    assert writes == {
        "0": [("v", f"writes:{nested}")],
        "1": [("v", "writes:poke")],
    }


def _state(*results: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(rule_results=list(results))


def test_runtime_rules_skipped_counts_only_skips_for_missing_dynamic() -> None:
    disabled = {"reason": "dynamic_checks_disabled"}
    states = [
        _state(
            SimpleNamespace(status="SKIPPED", details=disabled),
            SimpleNamespace(status="SKIPPED", details={"reason": "other"}),
            SimpleNamespace(status="SKIPPED", details=None),
        ),
        _state(
            SimpleNamespace(status="SKIPPED", details=disabled),
            SimpleNamespace(status="OK", details=disabled),
        ),
        _state(),
    ]

    assert count_runtime_rules_skipped(states) == 2
    assert count_runtime_rules_skipped([]) == 0


def test_runtime_results_unverified_counts_passes_with_something_unchecked() -> None:
    states = [
        _state(
            SimpleNamespace(status="OK", details={"unverified": ["case_raised"]}),
            SimpleNamespace(status="OK", details={"unverified": []}),
            SimpleNamespace(status="OK", details=None),
        ),
        _state(SimpleNamespace(status="OK", details={"unverified": ["x", "y"]})),
    ]

    assert count_runtime_results_unverified(states) == 2
    assert count_runtime_results_unverified([]) == 0


def test_new_builds_a_class_of_a_module_inside_a_subpackage(tmp_path: Path) -> None:
    # A $new translated to a class the target keeps in domain/services.py.
    package = tmp_path / "nested_pkg"
    (package / "domain").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "domain" / "__init__.py").write_text("", encoding="utf-8")
    (package / "domain" / "services.py").write_text(
        "class Service:\n    pass\n", encoding="utf-8"
    )
    (package / "target.py").write_text(
        "def place(service):\n    return type(service).__name__\n", encoding="utf-8"
    )

    outcome = run_cases(
        target_root=package,
        module_path="target",
        qualname="place",
        kind="function",
        cases=[{"args": [{"$new": "domain.services.Service"}]}],
        init=None,
        timeout_s=10.0,
        observe={"calls": True},
    )

    assert outcome.status == "completed"
    assert outcome.cases[0]["status"] == "passed", outcome.cases[0]["failures"]


_LAZY = """
import asyncio

from . import store


async def place(value):
    await asyncio.sleep(0)
    return store.save(value)


def rows(count):
    for index in range(count):
        yield store.save(index)


async def stream(count):
    for index in range(count):
        await asyncio.sleep(0)
        yield store.save(index)
"""


@pytest.fixture
def lazy_root(tmp_path: Path) -> Path:
    package = tmp_path / "lazy_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "store.py").write_text(
        "def save(value):\n    return value\n", encoding="utf-8"
    )
    (package / "target.py").write_text(textwrap.dedent(_LAZY), encoding="utf-8")
    return package


@pytest.mark.parametrize(
    ("qualname", "args"),
    [("place", [1]), ("rows", [2]), ("stream", [2])],
)
def test_the_body_of_a_coroutine_or_generator_runs_and_is_observed(
    lazy_root: Path, qualname: str, args: list
) -> None:
    # Calling it only creates the coroutine or generator; unless the probe
    # runs it, nothing is observed and the rule passes vacuously.
    outcome = run_cases(
        target_root=lazy_root,
        module_path="target",
        qualname=qualname,
        kind="function",
        cases=[{"args": args}],
        init=None,
        timeout_s=10.0,
        observe={"calls": True},
    )

    case = outcome.cases[0]
    assert case["status"] == "passed", case["failures"]
    assert "store" in {call["module"] for call in case["calls"]}
    assert case["lines"]["missed"] == []
