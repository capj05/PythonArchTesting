"""Verdicts of the DYN008 pattern evaluator on observed probe outcomes.

The probe outcome is placed in the batch cache, so these tests judge recorded
identity, notification and delegation without starting a child interpreter.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from pythonarchtesting.dynamic.batch import cache_key
from pythonarchtesting.dynamic.runner import ProbeOutcome
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.execution.evaluators.registry import get_rule_evaluator
from pythonarchtesting.execution.evaluators.runtime_structure import (
    RuntimePatternEvaluator,
)
from pythonarchtesting.matching import MatchStatus
from pythonarchtesting.rules.compilation import compile_rules

_HEADER = """
from typing import Annotated
from pythonarchtesting.rules import (
    enforce_runtime_observer,
    is_runtime_singleton,
    require_runtime_delegation,
)
"""

_SINGLETON = 'is_runtime_singleton(access="instance", cases=[{}])'
_CONSTRUCTOR_SINGLETON = "is_runtime_singleton(cases=[{}, {}])"
_OBSERVER = (
    'enforce_runtime_observer(subscribe="subscribe", notify="publish", '
    'unsubscribe="unsubscribe", cases=[{}])'
)
_DELEGATION = (
    'require_runtime_delegation("strategy", member="apply", '
    'cases=[{"args": [{"$spy": "strategy"}]}])'
)
_ANY_DELEGATION = (
    'require_runtime_delegation("strategy", cases=[{"args": [{"$spy": "strategy"}]}])'
)


def _rule_and_entity(marker: str) -> tuple[Any, Any]:
    holder = (
        f"def run(strategy):\n    __archtest__: Annotated[None, {marker}]\n"
        if marker.startswith("require_runtime_delegation")
        else f"class Subject:\n    __archtest__: Annotated[None, {marker}]\n"
    )
    entities = extract_entities_from_source(
        textwrap.dedent(_HEADER) + holder,
        Path("patterns.py"),
        Path("."),
        None,
        role="source",
        include_nested_functions=False,
        root_label="source",
    )
    rules, evidence, _ = compile_rules(entities, Mock())
    assert evidence == []
    entity = next(e for e in entities if e.name in {"Subject", "run"})
    return rules[0], entity


def _evaluate(
    marker: str,
    outcome: ProbeOutcome | None,
    target_root: Path | None = Path("."),
    target_kind: str | None = None,
):
    rule, entity = _rule_and_entity(marker)
    ctx = SimpleNamespace(target_root=target_root, dynamic_cache={}, sandbox=None)
    if outcome is not None:
        ctx.dynamic_cache[cache_key(rule, entity)] = outcome
    match = SimpleNamespace(status=MatchStatus.MATCHED, confidence=1.0)
    target = entity
    if target_kind is not None:
        target = SimpleNamespace(**{**vars(entity), "kind": target_kind})
    return get_rule_evaluator(rule.rule_type).evaluate(rule, entity, target, match, ctx)


def _cases(*cases: dict) -> ProbeOutcome:
    return ProbeOutcome(
        status="completed",
        cases=[
            {"index": index, "status": "passed", "failures": [], **case}
            for index, case in enumerate(cases)
        ],
    )


def test_the_registry_routes_the_pattern_rule_type() -> None:
    assert isinstance(get_rule_evaluator("runtime_pattern"), RuntimePatternEvaluator)


# --- singleton -----------------------------------------------------------


def test_one_shared_instance_passes() -> None:
    result = _evaluate(
        _SINGLETON,
        _cases({"singleton": {"access": "instance", "same": True, "type": "X"}}),
    )

    assert result.status == "OK"
    assert result.details["summary"] == "one shared instance in 1 case(s)"
    assert result.details["batched"] is True


def test_two_different_instances_fail() -> None:
    result = _evaluate(
        _CONSTRUCTOR_SINGLETON,
        _cases(
            {"singleton": {"access": "constructor", "same": True}},
            {"singleton": {"access": "constructor", "same": False}},
        ),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        "case 1: two accesses via constructor returned different objects"
    ]


def test_a_raising_access_fails_with_the_error() -> None:
    result = _evaluate(
        _SINGLETON,
        _cases(
            {"singleton": {"access": "instance", "error": "AttributeError: instance"}}
        ),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        "case 0: obtaining the instance via instance raised AttributeError: instance"
    ]


# --- observer ------------------------------------------------------------


def test_a_notified_and_forgotten_listener_passes() -> None:
    result = _evaluate(
        _OBSERVER,
        _cases(
            {"constructed": True, "observer": {"notified": 1, "after_unsubscribe": 0}}
        ),
    )

    assert result.status == "OK"
    assert result.details["summary"] == "listeners notified as declared in 1 case(s)"


def test_an_unnotified_and_unforgotten_listener_fails_twice() -> None:
    result = _evaluate(
        _OBSERVER,
        _cases(
            {"constructed": True, "observer": {"notified": 0, "after_unsubscribe": 2}}
        ),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        "case 0: a listener registered with subscribe() was not called by publish()",
        "case 0: the listener was still called after unsubscribe()",
    ]
    assert "(+1 more)" in result.message


def test_a_raising_subscription_fails_with_the_error() -> None:
    result = _evaluate(
        _OBSERVER,
        _cases({"constructed": True, "observer": {"error": "TypeError: closed"}}),
    )

    assert result.details["violations"] == [
        "case 0: subscribing or notifying raised TypeError: closed"
    ]


@pytest.mark.parametrize(
    ("raised", "detail"),
    [("ValueError: no bus", "ValueError: no bus"), (None, "no detail")],
)
def test_an_observer_subject_that_cannot_be_built_fails(
    raised: str | None, detail: str
) -> None:
    case: dict[str, Any] = {"constructed": False}
    if raised:
        case["raised"] = raised
    result = _evaluate(_OBSERVER, _cases(case))

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        f"case 0: the subject could not be built: {detail}"
    ]


# --- delegation ----------------------------------------------------------


def _spy_call(spy: str = "strategy", member: str = "apply") -> dict[str, Any]:
    return {"spy": spy, "member": member, "args": 1}


def test_a_call_to_the_spy_member_passes() -> None:
    result = _evaluate(_DELEGATION, _cases({"spy_calls": [_spy_call()]}))

    assert result.status == "OK"
    assert result.details["summary"] == "delegated to strategy in 1 case(s)"


def test_without_a_member_any_call_on_the_spy_passes() -> None:
    result = _evaluate(
        _ANY_DELEGATION, _cases({"spy_calls": [_spy_call(member="__call__")]})
    )

    assert result.status == "OK"


@pytest.mark.parametrize(
    "calls",
    [[], [_spy_call(member="other")], [_spy_call(spy="logger")]],
)
def test_no_call_to_the_spy_member_fails(calls: list) -> None:
    result = _evaluate(_DELEGATION, _cases({"spy_calls": calls}))

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        "case 0: never delegated to strategy.apply()"
    ]


def test_a_raising_call_is_named_in_the_violation() -> None:
    result = _evaluate(
        _ANY_DELEGATION, _cases({"spy_calls": [], "raised": "KeyError: 'x'"})
    )

    assert result.details["violations"] == [
        "case 0: never delegated to strategy; the call raised KeyError: 'x'"
    ]


def test_a_raising_call_after_delegating_still_passes() -> None:
    result = _evaluate(
        _DELEGATION, _cases({"spy_calls": [_spy_call()], "raised": "KeyError: 'x'"})
    )

    assert result.status == "OK"


# --- shared driver -------------------------------------------------------


@pytest.mark.parametrize("marker", [_SINGLETON, _OBSERVER, _DELEGATION])
def test_pattern_rules_are_skipped_without_dynamic(marker: str) -> None:
    result = _evaluate(marker, None, target_root=None)

    assert result.status == "SKIPPED"
    assert result.details["reason"] == "dynamic_checks_disabled"


def test_a_pattern_rule_on_a_target_of_another_kind_fails() -> None:
    result = _evaluate(_SINGLETON, None, target_kind="function")

    assert result.status == "FAILED"
    assert result.details["reason"] == "target_kind_mismatch"


def test_a_case_that_cannot_be_set_up_fails_the_delegation_rule() -> None:
    outcome = ProbeOutcome(
        status="completed",
        cases=[{"index": 0, "status": "error", "failures": ["setup: bad"]}],
    )

    result = _evaluate(_DELEGATION, outcome)

    assert result.status == "FAILED"
    assert result.details["reason"] == "case_setup_failed"
