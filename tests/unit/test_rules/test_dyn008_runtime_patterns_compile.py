from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest

from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.rules.compilation import compile_rules
from pythonarchtesting.rules.compilation.decorators.runtime_structure import (
    _identifier_problem,
    _mentions_spy,
)

_HEADER = """
from typing import Annotated
from pythonarchtesting.rules import (
    enforce_runtime_observer,
    is_runtime_singleton,
    require_runtime_delegation,
)
"""


def _compile(marker: str, *, on: str = "class") -> tuple[list, list, list]:
    if on == "class":
        holder = f"class Subject:\n    __archtest__: Annotated[None, {marker}]\n"
    elif on == "method":
        holder = (
            "class Subject:\n"
            "    def run(self, value):\n"
            f"        __archtest__: Annotated[None, {marker}]\n"
            "        return value\n"
        )
    else:
        holder = (
            "def run(value):\n"
            f"    __archtest__: Annotated[None, {marker}]\n"
            "    return value\n"
        )
    entities = extract_entities_from_source(
        textwrap.dedent(_HEADER).strip() + "\n" + holder,
        Path("source_module.py"),
        Path("."),
        None,
        role="source",
        include_nested_functions=False,
        root_label="source",
    )
    return compile_rules(entities, Mock())


def _assert_sentinel(marker: str, param: str, reason: str, *, on: str = "class"):
    rules, evidence, _ = _compile(marker, on=on)

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert rules[0].params["param"] == param
    assert reason in rules[0].params["compiler_reason"]
    assert rules[0].rule_id.startswith("DYN008/")
    assert [item.type for item in evidence] == ["compiler_invalid_param"]


def test_singleton_compiles_with_its_access_method() -> None:
    rules, evidence, _ = _compile(
        'is_runtime_singleton(access="instance", cases=[{"args": []}])'
    )

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN008/is_runtime_singleton/v1"]
    rule = rules[0]
    assert rule.rule_type == "runtime_pattern"
    assert rule.scope == "class"
    assert rule.params["pattern"] == "singleton"
    assert rule.params["access"] == "instance"
    assert rule.params["cases"] == [{"args": []}]
    assert rule.params["fail_on_unmatched"] is True


def test_singleton_without_access_uses_the_constructor() -> None:
    rules, _, _ = _compile("is_runtime_singleton(cases=[{}])")

    assert rules[0].params["access"] is None


def test_observer_compiles_with_every_parameter() -> None:
    rules, evidence, _ = _compile(
        'enforce_runtime_observer(subscribe="attach", notify="emit", '
        'unsubscribe="detach", notify_args=["x", {"$new": "Event"}], '
        "cases=[{}])"
    )

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN008/enforce_runtime_observer/v1"]
    params = rules[0].params
    assert params["pattern"] == "observer"
    assert (params["subscribe"], params["notify"], params["unsubscribe"]) == (
        "attach",
        "emit",
        "detach",
    )
    assert params["notify_args"] == ["x", {"$new": "Event"}]


def test_observer_notify_args_default_to_an_empty_list() -> None:
    rules, _, _ = _compile(
        'enforce_runtime_observer(subscribe="a", notify="b", cases=[{}])'
    )

    assert rules[0].params["notify_args"] == []
    assert rules[0].params["subscribe_args"] == []
    assert rules[0].params["unsubscribe"] is None


def test_observer_keyed_by_event_keeps_its_subscribe_args() -> None:
    rules, evidence, _ = _compile(
        'enforce_runtime_observer(subscribe="on", notify="emit", '
        'subscribe_args=["created"], notify_args=["created"], cases=[{}])'
    )

    assert evidence == []
    assert rules[0].params["subscribe_args"] == ["created"]


@pytest.mark.parametrize(
    ("subscribe_args", "reason"),
    [
        ('"created"', "subscribe_args must be a list"),
        ("[b'x']", "subscribe_args: bytes value"),
    ],
)
def test_unusable_subscribe_args_compile_to_a_sentinel(
    subscribe_args: str, reason: str
) -> None:
    _assert_sentinel(
        f'enforce_runtime_observer(subscribe="a", notify="b", '
        f"subscribe_args={subscribe_args}, cases=[{{}}])",
        "subscribe_args",
        reason,
    )


@pytest.mark.parametrize("on", ["function", "method"])
def test_delegation_compiles_on_functions_and_methods(on: str) -> None:
    rules, evidence, _ = _compile(
        'require_runtime_delegation("strategy", member="apply", '
        'cases=[{"args": [{"$spy": "strategy"}]}])',
        on=on,
    )

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN008/require_runtime_delegation/v1"]
    params = rules[0].params
    assert rules[0].scope == on
    assert (params["pattern"], params["spy"], params["member"]) == (
        "delegation",
        "strategy",
        "apply",
    )


def test_a_spy_injected_through_init_counts() -> None:
    rules, evidence, _ = _compile(
        'require_runtime_delegation("strategy", '
        'init={"args": [{"$spy": "strategy"}]}, cases=[{"args": [1]}])',
        on="method",
    )

    assert evidence == []
    assert rules[0].params["init"] == {"args": [{"$spy": "strategy"}]}
    assert rules[0].params["member"] is None


def test_a_spy_inside_a_tuple_argument_counts() -> None:
    rules, evidence, _ = _compile(
        'require_runtime_delegation("s", cases=[{"args": [({"$spy": "s"}, 1)]}])',
        on="function",
    )

    assert evidence == []
    assert rules[0].rule_type == "runtime_pattern"


def test_a_spy_in_a_case_init_counts() -> None:
    rules, evidence, _ = _compile(
        'require_runtime_delegation("s", '
        'cases=[{"args": [1], "init": {"kwargs": {"x": {"$spy": "s"}}}}])',
        on="method",
    )

    assert evidence == []
    assert rules[0].rule_type == "runtime_pattern"


@pytest.mark.parametrize(
    ("marker", "on"),
    [
        ("is_runtime_singleton(cases=[{}])", "function"),
        ('enforce_runtime_observer(subscribe="a", notify="b", cases=[{}])', "method"),
        ('require_runtime_delegation("s", cases=[{"args": [{"$spy": "s"}]}])', "class"),
    ],
)
def test_a_wrong_kind_is_an_invalid_target(marker: str, on: str) -> None:
    rules, evidence, _ = _compile(marker, on=on)

    assert rules == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


@pytest.mark.parametrize(
    ("marker", "param", "reason", "on"),
    [
        (
            'is_runtime_singleton(access="get instance", cases=[{}])',
            "access",
            "access must be a method name",
            "class",
        ),
        (
            "is_runtime_singleton(access=3, cases=[{}])",
            "access",
            "method name",
            "class",
        ),
        (
            'enforce_runtime_observer(subscribe="", notify="b", cases=[{}])',
            "subscribe",
            "subscribe must be a method name",
            "class",
        ),
        (
            "enforce_runtime_observer(notify='b', cases=[{}])",
            "subscribe",
            "method name",
            "class",
        ),
        (
            'enforce_runtime_observer(subscribe="a", notify="1x", cases=[{}])',
            "notify",
            "notify must be a method name",
            "class",
        ),
        (
            'enforce_runtime_observer(subscribe="a", notify="b", '
            'unsubscribe="a.b", cases=[{}])',
            "unsubscribe",
            "unsubscribe must be a method name",
            "class",
        ),
        (
            'require_runtime_delegation("s", member="do it", '
            'cases=[{"args": [{"$spy": "s"}]}])',
            "member",
            "member must be a method name",
            "function",
        ),
        (
            'require_runtime_delegation("", cases=[{"args": [{"$spy": ""}]}])',
            "spy",
            "name of the spy",
            "function",
        ),
    ],
)
def test_bad_identifiers_compile_to_a_sentinel(
    marker: str, param: str, reason: str, on: str
) -> None:
    _assert_sentinel(marker, param, reason, on=on)


@pytest.mark.parametrize(
    ("notify_args", "reason"),
    [
        ('"event"', "notify_args must be a list"),
        ("0", "notify_args must be a list"),
        ('("a",)', "notify_args must be a list"),
        ("[{1: 2}]", "notify_args: dict key 1 is not a string"),
        ("[b'x']", "notify_args: bytes value"),
    ],
)
def test_unusable_notify_args_compile_to_a_sentinel(
    notify_args: str, reason: str
) -> None:
    _assert_sentinel(
        f'enforce_runtime_observer(subscribe="a", notify="b", '
        f"notify_args={notify_args}, cases=[{{}}])",
        "notify_args",
        reason,
    )


@pytest.mark.parametrize(
    "marker",
    [
        'require_runtime_delegation("strategy", cases=[{"args": [1]}])',
        'require_runtime_delegation("strategy", cases=[{"args": [{"$spy": "other"}]}])',
    ],
)
def test_a_spy_missing_from_the_cases_compiles_to_a_sentinel(marker: str) -> None:
    _assert_sentinel(
        marker, "cases", 'no case passes {"$spy": "strategy"}', on="function"
    )


@pytest.mark.parametrize(
    ("marker", "on"),
    [
        ('is_runtime_singleton(cases=[{"returns": 1}])', "class"),
        (
            'enforce_runtime_observer(subscribe="a", notify="b", '
            'cases=[{"expect": 1}])',
            "class",
        ),
        (
            'require_runtime_delegation("s", '
            'cases=[{"args": [{"$spy": "s"}], "returns": 1}])',
            "function",
        ),
    ],
)
def test_unknown_case_keys_compile_to_a_sentinel(marker: str, on: str) -> None:
    _assert_sentinel(marker, "cases", "unknown keys", on=on)


def test_malformed_delegation_cases_are_not_reported_as_a_missing_spy() -> None:
    _assert_sentinel(
        'require_runtime_delegation("s", cases=[])',
        "cases",
        "non-empty list",
        on="function",
    )


def test_singleton_cases_cannot_carry_init() -> None:
    _assert_sentinel(
        'is_runtime_singleton(cases=[{"init": {"args": []}}])',
        "cases",
        "only methods support",
    )


def test_identifier_problem_and_spy_search_helpers() -> None:
    assert _identifier_problem({}, "access", required=False) is None
    assert _identifier_problem({"access": "get"}, "access", required=True) is None
    assert _identifier_problem({}, "notify", required=True) == (
        "notify",
        "notify must be a method name",
    )
    assert _mentions_spy([{"args": [[{"$spy": "s"}]]}], "s") is True
    # A tuple reaches the child as a JSON list, so its spy is injected too.
    assert _mentions_spy([{"args": [({"$spy": "s"},)]}], "s") is True
    assert _mentions_spy({"kwargs": {"x": {"$spy": "t"}}}, "s") is False
    assert _mentions_spy([None, "s"], "s") is False
