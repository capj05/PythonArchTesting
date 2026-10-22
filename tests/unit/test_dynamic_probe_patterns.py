"""In-process tests for the probe's design-pattern checks (DYN008).

The classes live in a throwaway module built under ``tmp_path``. The probe
reports identity, notification and delegation, never what a call computes.
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
class Shared:
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def fresh(cls):
        return cls()

    @classmethod
    def broken(cls):
        raise RuntimeError("not ready")


class Event:
    def __init__(self, name="e"):
        self.name = name


class Bus:
    def __init__(self, fail=False):
        if fail:
            raise ValueError("no bus")
        self.listeners = []
        self.seen = []

    def subscribe(self, listener):
        self.listeners.append(listener)

    def unsubscribe(self, listener):
        self.listeners.remove(listener)

    def ignore(self, listener):
        pass

    def refuse(self, listener):
        raise TypeError("closed")

    def publish(self, *args):
        self.seen.extend(type(arg).__name__ for arg in args)
        for listener in self.listeners:
            listener(*args)

    def publish_update(self, *args):
        for listener in self.listeners:
            listener.update(*args)

    def silent(self, *args):
        pass


class TopicBus:
    def __init__(self):
        self.listeners = {}

    def on(self, topic, listener):
        self.listeners.setdefault(topic, []).append(listener)

    def off(self, topic, listener):
        self.listeners[topic].remove(listener)

    def emit(self, topic, *args):
        for listener in self.listeners.get(topic, []):
            listener(*args)


class Config:
    pass


_CONFIG = None


def get_config():
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = Config()
    return _CONFIG


def new_config():
    return Config()


def apply(strategy, value):
    return strategy.apply(value)


def ignore(strategy, value):
    return value


def call_it(fn, value):
    return fn(value, extra=1)


class Calculator:
    def __init__(self, strategy):
        self.strategy = strategy

    def total(self, value):
        return self.strategy.apply(value)
"""


@pytest.fixture
def module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    filename = tmp_path / "patterns_mod.py"
    module = types.ModuleType("patterns_mod")
    module.__file__ = str(filename)
    monkeypatch.setitem(sys.modules, "patterns_mod", module)
    exec(  # nosec B102
        compile(textwrap.dedent(_SOURCE), str(filename), "exec"), module.__dict__
    )
    return module


@pytest.fixture(autouse=True)
def _clean_spy_calls() -> Any:
    probe._SPY_CALLS.clear()
    yield
    probe._SPY_CALLS.clear()


def _run(
    module: types.ModuleType,
    qualname: str,
    case: dict[str, Any] | None = None,
    *,
    kind: str = "class",
    **observe: Any,
) -> dict[str, Any]:
    request = {"qualname": qualname, "kind": kind, "observe": observe}
    return probe._run_case(0, case or {}, request, module, None)


# --- _Spy ----------------------------------------------------------------


def test_a_spy_records_calls_and_attribute_methods() -> None:
    spy = probe._Spy("strategy")

    assert spy(1, 2, key=3) == 1
    assert spy.apply("x") == "x"
    assert spy.reset() is None

    assert probe._SPY_CALLS == [
        {"spy": "strategy", "member": "__call__", "args": 3},
        {"spy": "strategy", "member": "apply", "args": 1},
        {"spy": "strategy", "member": "reset", "args": 0},
    ]


def test_a_spy_has_no_dunder_attributes_and_a_readable_repr() -> None:
    spy = probe._Spy("listener")

    with pytest.raises(AttributeError):
        _ = spy.__wrapped__
    assert not hasattr(spy, "__len__")
    assert repr(spy) == "<spy listener>"
    assert probe._SPY_CALLS == []


def test_spy_markers_are_built_anywhere_in_a_value(module: types.ModuleType) -> None:
    value = probe._build_value(
        {"a": [{"$spy": "s"}], "b": {"$new": "Event", "args": [{"$spy": "t"}]}},
        vars(module),
        None,
    )

    assert repr(value["a"][0]) == "<spy s>"
    assert repr(value["b"].name) == "<spy t>"


# --- _SPY_CALLS lifetime -------------------------------------------------


def test_spy_calls_are_reported_and_cleared_between_cases(
    module: types.ModuleType,
) -> None:
    request = {"qualname": "apply", "kind": "function", "observe": {"spies": True}}
    first = probe._run_case(
        0, {"args": [{"$spy": "strategy"}, 1]}, request, module, None
    )
    second = probe._run_case(1, {"args": [{"$spy": "other"}, 2]}, request, module, None)

    assert first["spy_calls"] == [{"spy": "strategy", "member": "apply", "args": 1}]
    assert second["spy_calls"] == [{"spy": "other", "member": "apply", "args": 1}]


def test_spy_calls_are_not_reported_without_the_observation(
    module: types.ModuleType,
) -> None:
    outcome = _run(module, "apply", {"args": [{"$spy": "s"}, 1]}, kind="function")

    assert "spy_calls" not in outcome


def test_class_inspection_starts_with_no_spy_calls(module: types.ModuleType) -> None:
    probe._SPY_CALLS.append({"spy": "stale", "member": "x", "args": 0})

    _run(module, "Event", construct=False)

    assert probe._SPY_CALLS == []


def test_spy_calls_do_not_leak_between_batch_jobs(
    module: types.ModuleType, tmp_path: Path
) -> None:
    writes = probe.WriteRecorder(str(tmp_path))

    def job(spy: str) -> dict[str, Any]:
        return {
            "qualname": "apply",
            "kind": "function",
            "cases": [{"args": [{"$spy": spy}, 1]}],
            "observe": {"spies": True},
            "timeout_s": 5.0,
        }

    first = probe._run_job(job("a"), module, None, writes)
    second = probe._run_job(job("b"), module, None, writes)

    assert [c["spy"] for c in first["cases"][0]["spy_calls"]] == ["a"]
    assert [c["spy"] for c in second["cases"][0]["spy_calls"]] == ["b"]


def test_a_spy_passed_to_a_method_through_init_is_seen(
    module: types.ModuleType,
) -> None:
    outcome = _run(
        module,
        "Calculator.total",
        {"args": [3], "init": {"args": [{"$spy": "strategy"}]}},
        kind="method",
        spies=True,
    )

    assert outcome["spy_calls"] == [{"spy": "strategy", "member": "apply", "args": 1}]


def test_keyword_arguments_count_towards_the_spy_call_arity(
    module: types.ModuleType,
) -> None:
    outcome = _run(
        module, "call_it", {"args": [{"$spy": "fn"}, 1]}, kind="function", spies=True
    )

    assert outcome["spy_calls"] == [{"spy": "fn", "member": "__call__", "args": 2}]


# --- _check_singleton ----------------------------------------------------


@pytest.mark.parametrize(
    ("access", "same"),
    [("instance", True), ("fresh", False), (None, False)],
)
def test_singleton_reports_whether_both_accesses_match(
    module: types.ModuleType, access: str | None, same: bool
) -> None:
    outcome = _run(module, "Shared", construct=False, singleton={"access": access})

    assert outcome["singleton"] == {
        "access": access or "constructor",
        "same": same,
        "type": "Shared",
    }
    assert "constructed" not in outcome


def test_singleton_reports_a_raising_access(module: types.ModuleType) -> None:
    outcome = _run(module, "Shared", construct=False, singleton={"access": "broken"})

    assert outcome["singleton"] == {
        "access": "broken",
        "error": "RuntimeError: not ready",
    }


def test_singleton_reports_a_missing_access(module: types.ModuleType) -> None:
    result = probe._check_singleton(module.Shared, {"access": "nope"}, [], {})

    assert result["access"] == "nope"
    assert result["error"].startswith("AttributeError:")
    assert "same" not in result


def test_singleton_passes_case_arguments_to_the_access(
    module: types.ModuleType,
) -> None:
    result = probe._check_singleton(module.Event, {}, ["x"], {})

    assert result == {"access": "constructor", "same": False, "type": "Event"}


# --- _check_observer -----------------------------------------------------


def _observer(**spec: Any) -> dict[str, Any]:
    return {"subscribe": "subscribe", "notify": "publish", **spec}


def test_observer_reports_a_notified_listener(module: types.ModuleType) -> None:
    outcome = _run(module, "Bus", observer=_observer(notify_args=["e"]))

    assert outcome["constructed"] is True
    assert outcome["observer"] == {"notified": 1}


def test_observer_counts_calls_to_a_listener_method(
    module: types.ModuleType,
) -> None:
    outcome = _run(module, "Bus", observer=_observer(notify="publish_update"))

    assert outcome["observer"] == {"notified": 1}


def test_observer_reports_a_listener_that_is_never_called(
    module: types.ModuleType,
) -> None:
    outcome = _run(module, "Bus", observer=_observer(notify="silent"))

    assert outcome["observer"] == {"notified": 0}


@pytest.mark.parametrize(("unsubscribe", "after"), [("unsubscribe", 0), ("ignore", 1)])
def test_observer_checks_unsubscribe(
    module: types.ModuleType, unsubscribe: str, after: int
) -> None:
    outcome = _run(module, "Bus", observer=_observer(unsubscribe=unsubscribe))

    assert outcome["observer"] == {"notified": 1, "after_unsubscribe": after}


def test_observer_reports_a_raising_subscribe(module: types.ModuleType) -> None:
    outcome = _run(module, "Bus", observer=_observer(subscribe="refuse"))

    assert outcome["observer"] == {"error": "TypeError: closed"}


def test_observer_reports_a_missing_notify_method(module: types.ModuleType) -> None:
    outcome = _run(module, "Bus", observer=_observer(notify="nope"))

    assert outcome["observer"]["error"].startswith("AttributeError:")


def test_observer_builds_notify_args_with_new(module: types.ModuleType) -> None:
    bus = module.Bus()
    result = probe._check_observer(
        bus,
        _observer(notify_args=[{"$new": "Event", "args": ["placed"]}, 2]),
        vars(module),
        None,
    )

    assert result == {"notified": 1}
    assert bus.seen == ["Event", "int"]


def test_observer_reports_notify_args_that_cannot_be_built(
    module: types.ModuleType,
) -> None:
    result = probe._check_observer(
        module.Bus(), _observer(notify_args=[{"$new": "Missing"}]), vars(module), None
    )

    assert "cannot resolve 'Missing'" in result["error"]


def test_observer_is_not_checked_when_the_subject_cannot_be_built(
    module: types.ModuleType,
) -> None:
    outcome = _run(module, "Bus", {"kwargs": {"fail": True}}, observer=_observer())

    assert outcome["constructed"] is False
    assert outcome["raised"] == "ValueError: no bus"
    assert "observer" not in outcome


# --- keyed observers and module-level accessors ----------------------------


def test_an_observer_keyed_by_topic_is_subscribed_with_the_topic(
    module: types.ModuleType,
) -> None:
    spec = {
        "subscribe": "on",
        "notify": "emit",
        "unsubscribe": "off",
        "subscribe_args": ["created"],
        "notify_args": ["created", 1],
    }

    outcome = _run(module, "TopicBus", observer=spec)

    assert outcome["observer"] == {"notified": 1, "after_unsubscribe": 0}


def test_a_keyed_observer_that_misses_the_topic_is_not_notified(
    module: types.ModuleType,
) -> None:
    spec = {
        "subscribe": "on",
        "notify": "emit",
        "subscribe_args": ["created"],
        "notify_args": ["deleted"],
    }

    assert _run(module, "TopicBus", observer=spec)["observer"] == {"notified": 0}


@pytest.mark.parametrize(
    ("access", "same"), [("get_config", True), ("new_config", False)]
)
def test_a_singleton_may_be_obtained_through_a_function_of_its_module(
    module: types.ModuleType, access: str, same: bool
) -> None:
    outcome = _run(module, "Config", construct=False, singleton={"access": access})

    assert outcome["singleton"]["same"] is same
    assert outcome["singleton"]["access"] == access
