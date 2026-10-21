"""Verdicts of the DYN005 / DYN006 / DYN007 evaluators on observed class shapes.

The probe outcome is placed in the batch cache, so these tests judge recorded
members and abstractness without starting a child interpreter.
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
    RuntimeClassKindEvaluator,
    RuntimeMembersEvaluator,
    RuntimeProtocolEvaluator,
)
from pythonarchtesting.matching import MatchStatus
from pythonarchtesting.rules.compilation import compile_rules

_HEADER = """
from typing import Annotated, Protocol
from pythonarchtesting.rules import (
    forbid_runtime_members,
    implements_runtime_protocol,
    is_runtime_abstract_class,
    is_runtime_concrete_class,
    require_runtime_members,
)

class Exporter(Protocol):
    name: str

    def export(self, rows): ...
"""


def _rule_and_entity(marker: str) -> tuple[Any, Any]:
    source = textwrap.dedent(_HEADER) + textwrap.dedent(f"""
        class Subject:
            __archtest__: Annotated[None, {marker}]
        """)
    entities = extract_entities_from_source(
        source,
        Path("shapes.py"),
        Path("."),
        None,
        role="source",
        include_nested_functions=False,
        root_label="source",
    )
    rules, evidence, _ = compile_rules(entities, Mock())
    assert evidence == []
    entity = next(e for e in entities if e.name == "Subject")
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
    evaluator = get_rule_evaluator(rule.rule_type)
    return evaluator.evaluate(rule, entity, target, match, ctx)


def _cases(*cases: dict) -> ProbeOutcome:
    return ProbeOutcome(
        status="completed",
        cases=[
            {"index": index, "status": "passed", "failures": [], **case}
            for index, case in enumerate(cases)
        ],
    )


def _present(where: str = "instance", **extra: Any) -> dict[str, Any]:
    return {"present": True, "where": where, **extra}


_REQUIRE = 'require_runtime_members("host", "port", cases=[{}, {}])'
_FORBID = 'forbid_runtime_members("password", cases=[{}])'


def test_the_registry_routes_each_class_rule_type() -> None:
    assert isinstance(get_rule_evaluator("runtime_members"), RuntimeMembersEvaluator)
    assert isinstance(
        get_rule_evaluator("runtime_class_kind"), RuntimeClassKindEvaluator
    )
    assert isinstance(get_rule_evaluator("runtime_protocol"), RuntimeProtocolEvaluator)


def test_require_members_passes_when_every_instance_has_them() -> None:
    members = {"host": _present(), "port": _present("shapes.Defaults")}
    result = _evaluate(
        _REQUIRE,
        _cases(
            {"constructed": True, "members": members},
            {"constructed": True, "members": members},
        ),
    )

    assert result.status == "OK"
    assert result.details["summary"] == "every instance has host, port (2 case(s))"


def test_require_members_fails_per_case_and_missing_name() -> None:
    result = _evaluate(
        _REQUIRE,
        _cases(
            {"constructed": True, "members": {"host": _present()}},
            {"constructed": True, "members": {"host": {"present": False}}},
        ),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        "case 0: the instance has no 'port'",
        "case 1: the instance has no 'host'",
        "case 1: the instance has no 'port'",
    ]
    assert "(+2 more)" in result.message


def test_forbid_members_names_where_the_member_comes_from() -> None:
    result = _evaluate(
        _FORBID,
        _cases(
            {"constructed": True, "members": {"password": _present("shapes.Mixin")}}
        ),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        "case 0: the instance has 'password' (from shapes.Mixin)"
    ]


def test_forbid_members_passes_without_them() -> None:
    result = _evaluate(
        _FORBID,
        _cases({"constructed": True, "members": {"password": {"present": False}}}),
    )

    assert result.status == "OK"
    assert result.details["summary"] == "no instance has password (1 case(s))"


@pytest.mark.parametrize("marker", [_REQUIRE, _FORBID])
def test_members_fail_when_the_instance_cannot_be_built(marker: str) -> None:
    result = _evaluate(
        marker, _cases({"constructed": False, "raised": "ValueError: bad"})
    )

    assert result.status == "FAILED"
    assert result.details["violations"][0] == (
        "case 0: the instance could not be built: ValueError: bad"
    )


_CONCRETE = 'is_runtime_concrete_class(cases=[{"args": [1]}])'
_ABSTRACT = "is_runtime_abstract_class()"


def test_a_constructed_concrete_class_passes() -> None:
    result = _evaluate(_CONCRETE, _cases({"abstract": False, "constructed": True}))

    assert result.status == "OK"
    assert result.details["summary"] == "instantiable in 1 case(s)"


def test_a_class_abstract_at_run_time_fails_the_concrete_rule() -> None:
    result = _evaluate(
        _CONCRETE,
        _cases(
            {
                "abstract": True,
                "abstract_methods": ["__iter__", "__len__"],
                "constructed": False,
                "raised": "TypeError: abstract",
            }
        ),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        "case 0: the class is abstract at run time; unimplemented: __iter__, __len__"
    ]


def test_a_concrete_class_whose_constructor_raises_fails() -> None:
    result = _evaluate(
        _CONCRETE,
        _cases({"abstract": False, "constructed": False, "raised": None}),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == ["case 0: constructing it raised no detail"]


def test_the_abstract_rule_never_asks_for_an_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pythonarchtesting.dynamic import runner

    seen: dict[str, Any] = {}

    def fake_run_cases(**kwargs: Any) -> ProbeOutcome:
        seen.update(kwargs)
        return _cases({"abstract": True, "abstract_methods": ["save"]})

    monkeypatch.setattr(runner, "run_cases", fake_run_cases)

    result = _evaluate(_ABSTRACT, None)

    assert result.status == "OK"
    assert result.details["summary"] == "the class is abstract at run time"
    assert result.details["batched"] is False
    assert seen["observe"] == {"construct": False}
    assert seen["kind"] == "class"
    assert seen["cases"] == [{}]


def test_a_concrete_class_fails_the_abstract_rule() -> None:
    result = _evaluate(_ABSTRACT, _cases({"abstract": False, "abstract_methods": []}))

    assert result.status == "FAILED"
    assert "the class is concrete at run time" in result.details["summary"]


_PROTOCOL = 'implements_runtime_protocol(Exporter, cases=[{"args": [";"]}])'


def _export(**extra: Any) -> dict[str, Any]:
    return _present("shapes.Subject", **extra)


def test_an_instance_with_every_protocol_member_passes() -> None:
    result = _evaluate(
        _PROTOCOL,
        _cases(
            {
                "constructed": True,
                "members": {
                    "name": _present("shapes.Subject"),
                    "export": _export(callable=True, bindable=True),
                },
            }
        ),
    )

    assert result.status == "OK"
    assert result.details["summary"] == (
        "instances provide every member of shapes.Exporter (1 case(s))"
    )


@pytest.mark.parametrize(
    ("export", "violation"),
    [
        ({"present": False}, "case 0: no method 'export'"),
        (_export(callable=False), "case 0: 'export' is not callable"),
        (
            _export(callable=True, bindable=False),
            "case 0: 'export' does not accept 1 positional argument(s)",
        ),
    ],
)
def test_protocol_methods_must_exist_be_callable_and_accept_the_arguments(
    export: dict[str, Any], violation: str
) -> None:
    result = _evaluate(
        _PROTOCOL,
        _cases(
            {
                "constructed": True,
                "members": {"name": {"present": False}, "export": export},
            }
        ),
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == ["case 0: no attribute 'name'", violation]


def test_the_protocol_rule_fails_when_the_instance_cannot_be_built() -> None:
    result = _evaluate(
        _PROTOCOL, _cases({"constructed": False, "raised": "TypeError: args"})
    )

    assert result.status == "FAILED"
    assert result.details["violations"] == [
        "case 0: the instance could not be built: TypeError: args"
    ]


@pytest.mark.parametrize("marker", [_REQUIRE, _CONCRETE, _PROTOCOL])
def test_a_class_rule_matched_to_a_function_fails(marker: str) -> None:
    result = _evaluate(marker, None, target_kind="function")

    assert result.status == "FAILED"
    assert result.details["reason"] == "target_kind_mismatch"


@pytest.mark.parametrize("marker", [_FORBID, _ABSTRACT, _PROTOCOL])
def test_class_rules_are_skipped_without_dynamic(marker: str) -> None:
    result = _evaluate(marker, None, target_root=None)

    assert result.status == "SKIPPED"


def test_a_class_case_that_cannot_be_set_up_fails_the_rule() -> None:
    result = _evaluate(
        _CONCRETE,
        _cases({"status": "error", "failures": ["setup: 'X' is not a class"]}),
    )

    assert result.status == "FAILED"
    assert result.details["reason"] == "case_setup_failed"
    assert "case 0 could not run: setup: 'X' is not a class" in result.message
