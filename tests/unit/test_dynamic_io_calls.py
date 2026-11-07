"""I/O through builtins is a call into a layer, like a call into ``sqlite3``.

``len()`` or ``list.append()`` belong to no layer and stay unrecorded, but
``open()`` does file I/O and ``print()``/``input()`` talk to the console: a
domain layer that must not do I/O can forbid them with
``forbid_runtime_calls("io")`` (``open`` is ``io.open``) and
``forbid_runtime_calls("builtins.print", "builtins.input")``.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from pythonarchtesting.dynamic.runner import run_cases

from .test_dynamic_evaluators import _call, _cases, _evaluate, _rule_and_entity

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


_BRANCHING = """
def describe(shape):
    if isinstance(shape, int):
        return "int"
    if type(shape) is str:
        return "str"
    return print(len([shape])) or "other"
"""


def test_probe_records_isinstance_only_when_forbidden(tmp_path: Path) -> None:
    """``isinstance()`` and ``type()`` are recorded only when a rule names
    them (``builtins.isinstance``, ``builtins.type``): branching on the type
    is then a call into a layer; else they belong to no layer, like ``len()``,
    and the report does not grow with them."""
    from pythonarchtesting.dynamic.batch import observation

    package = tmp_path / "shapes_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "target.py").write_text(_BRANCHING, encoding="utf-8")
    forbidding, _ = _rule_and_entity(
        'forbid_runtime_calls("builtins.isinstance", "builtins.type", ' "cases=[{}])"
    )
    printing, _ = _rule_and_entity('forbid_runtime_calls("builtins", cases=[{}])')
    assert observation(forbidding) == {
        "calls": True,
        "builtins": ["isinstance", "type"],
    }
    assert observation(printing) == {"calls": True}

    def recorded(observe: dict) -> set[tuple[str, str]]:
        outcome = run_cases(
            target_root=package,
            module_path="target",
            qualname="describe",
            kind="function",
            cases=[{"args": [1]}, {"args": ["x"]}, {"args": [1.5]}],
            init=None,
            timeout_s=10.0,
            observe=observe,
        )
        return {
            (call["module"], call["callee"])
            for case in outcome.cases
            for call in case["calls"]
        }

    assert recorded(observation(printing)) == {("builtins", "print")}
    watched = recorded(observation(forbidding))
    assert ("builtins", "isinstance") in watched
    assert ("builtins", "print") in watched
    if sys.version_info >= (3, 12):  # type() is seen through sys.monitoring
        assert ("builtins", "type") in watched
    assert ("builtins", "len") not in watched


def _type_recorder():
    from pythonarchtesting.dynamic import probe

    return probe.CallRecorder("caller_mod", None, builtins=("isinstance", "type"))


def test_type_calls_without_a_free_tool_id_are_reported_unobserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pythonarchtesting.dynamic import probe

    # Every id taken (by a debugger, coverage, a profiler, ...).
    taken = type("Monitoring", (), {"get_tool": staticmethod(lambda _: "someone")})
    monkeypatch.setattr(probe, "_monitoring", lambda: taken)
    recorder = _type_recorder()

    with recorder.watching():
        pass

    assert recorder.unobserved == {"builtins.type": "no free sys.monitoring tool id"}


def test_type_calls_without_sys_monitoring_are_reported_unobserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pythonarchtesting.dynamic import probe

    monkeypatch.setattr(probe, "_monitoring", lambda: None)
    recorder = _type_recorder()

    with recorder.watching():
        pass

    assert recorder.unobserved == {
        "builtins.type": "needs Python 3.12+ (sys.monitoring)"
    }


@pytest.mark.skipif(sys.version_info < (3, 12), reason="sys.monitoring")
def test_the_tool_id_is_tool_3_first_and_freed_after_an_exception() -> None:
    free_before = [i for i in range(6) if sys.monitoring.get_tool(i) is None]
    recorder = _type_recorder()

    with pytest.raises(RuntimeError):
        with recorder.watching():
            if 3 in free_before:
                assert sys.monitoring.get_tool(3) == "pythonarchtesting-probe"
            raise RuntimeError("boom")

    assert [i for i in range(6) if sys.monitoring.get_tool(i) is None] == free_before
    assert recorder.unobserved == {}


def test_a_pass_with_unobservable_calls_is_marked_unverified() -> None:
    result = _evaluate(
        'forbid_runtime_calls("builtins.isinstance", "builtins.type", cases=[{}])',
        _cases(
            {
                "calls": [],
                "unobserved": {"builtins.type": "no free sys.monitoring tool id"},
            }
        ),
    )

    assert result.status == "OK"
    assert result.details["unverified"] == ["calls_not_observable"]
    assert result.details["unobserved_calls"] == {
        "builtins.type": "no free sys.monitoring tool id"
    }
    assert "not observable: builtins.type() (no free" in result.message
