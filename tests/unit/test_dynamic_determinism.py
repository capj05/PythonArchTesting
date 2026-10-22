"""Two runs of the same target observe the same thing.

Iterating a set of strings follows their hashes, which Python randomises per
interpreter, and ``random`` is seeded from the clock: either would let the
order of calls — and with it a flow verdict — change from run to run.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pythonarchtesting.dynamic.runner import _child_environment, run_cases
from pythonarchtesting.dynamic.sandbox import SandboxPolicy

_STAGES = """
def alpha(): pass
def bravo(): pass
def charlie(): pass
def delta(): pass
def echo(): pass
def foxtrot(): pass
def golf(): pass
def hotel(): pass
"""

_TARGET = """
import random

from . import stages


def by_set():
    for name in {"alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"}:
        getattr(stages, name)()


def by_random():
    names = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"]
    random.shuffle(names)
    for name in names:
        getattr(stages, name)()
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    package = tmp_path / "order_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "stages.py").write_text(textwrap.dedent(_STAGES), encoding="utf-8")
    (package / "target.py").write_text(textwrap.dedent(_TARGET), encoding="utf-8")
    return package


def _order(root: Path, qualname: str) -> list[str]:
    outcome = run_cases(
        target_root=root,
        module_path="target",
        qualname=qualname,
        kind="function",
        cases=[{"args": []}, {"args": []}],
        init=None,
        timeout_s=10.0,
        observe={"calls": True},
    )
    assert outcome.status == "completed", outcome.error
    return [
        f"{case['index']}:{call['callee']}"
        for case in outcome.cases
        for call in case["calls"]
    ]


@pytest.mark.parametrize("qualname", ["by_set", "by_random"])
def test_the_order_of_calls_is_the_same_in_every_run(root: Path, qualname: str) -> None:
    first = _order(root, qualname)

    assert all(_order(root, qualname) == first for _ in range(4))


def test_every_case_starts_from_the_same_random_state(root: Path) -> None:
    order = _order(root, "by_random")

    first = [entry[2:] for entry in order if entry.startswith("0:")]
    second = [entry[2:] for entry in order if entry.startswith("1:")]
    assert first == second


@pytest.mark.parametrize("mode", ["none", "limits"])
def test_the_child_gets_no_python_variable_but_the_hash_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setenv("PYTHONPATH", "/somewhere/else")
    monkeypatch.setenv("PYTHONSTARTUP", "/somewhere/startup.py")

    environment = _child_environment(SandboxPolicy(mode=mode), tmp_path)

    assert {name for name in environment if name.startswith("PYTHON")} == {
        "PYTHONHASHSEED"
    }
    assert environment["PYTHONHASHSEED"] == "0"
