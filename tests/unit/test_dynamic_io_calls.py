"""I/O through builtins is a call into a layer, like a call into ``sqlite3``.

``len()`` or ``list.append()`` belong to no layer and stay unrecorded, but
``open()`` does file I/O and ``print()``/``input()`` talk to the console: a
domain layer that must not do I/O can forbid them with
``forbid_runtime_calls("io")`` (``open`` is ``io.open``) and
``forbid_runtime_calls("builtins.print", "builtins.input")``.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pythonarchtesting.dynamic.runner import run_cases

from .test_dynamic_evaluators import _call, _cases, _evaluate

_TARGET = """
def report(rows):
    print(len(rows))
    with open(__file__, encoding="utf-8") as handle:
        handle.readline()
    return sorted(rows)
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    package = tmp_path / "io_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "target.py").write_text(textwrap.dedent(_TARGET), encoding="utf-8")
    return package


def test_open_and_print_are_recorded_and_other_builtins_are_not(root: Path) -> None:
    outcome = run_cases(
        target_root=root,
        module_path="target",
        qualname="report",
        kind="function",
        cases=[{"args": [[2, 1]]}],
        init=None,
        timeout_s=10.0,
        observe={"calls": True},
    )

    calls = {(call["module"], call["callee"]) for call in outcome.cases[0]["calls"]}
    assert ("io", "open") in calls
    assert ("builtins", "print") in calls
    assert not {callee for module, callee in calls if callee in ("len", "sorted")}


_IO_FORBIDDEN = 'forbid_runtime_calls("io", "builtins.print", cases=[{"args": [1, 2]}])'


@pytest.mark.parametrize(
    ("call", "forbidden"),
    [
        (_call("io", "open"), True),
        (_call("builtins", "print"), True),
        (_call("builtins", "input"), False),
        (_call("service", "print"), False),
    ],
)
def test_a_builtin_is_forbidden_by_its_dotted_name(call: dict, forbidden: bool) -> None:
    result = _evaluate(_IO_FORBIDDEN, _cases({"calls": [call]}, {"calls": []}))

    assert (result.status == "FAILED") is forbidden
