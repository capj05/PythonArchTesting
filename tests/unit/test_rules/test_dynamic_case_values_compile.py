"""Compile-time checks of ``steps`` and ``{"$spy": ..., "returns": ...}`` in cases."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest

from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.rules.compilation import compile_rules

_IMPORTS = (
    "from typing import Annotated\n"
    "from pythonarchtesting.rules import (\n"
    "    forbid_runtime_calls, is_runtime_singleton, require_runtime_members,\n"
    ")\n"
)


def _compile(body: str) -> list:
    entities = extract_entities_from_source(
        _IMPORTS + textwrap.dedent(body).strip() + "\n",
        Path("source_module.py"),
        Path("."),
        None,
        role="source",
        include_nested_functions=False,
        root_label="source",
    )
    rules, _, _ = compile_rules(entities, Mock())
    return rules


def _on_method(cases: str) -> list:
    return _compile(f"""
class Cart:
    def checkout(self):
        __archtest__: Annotated[None, forbid_runtime_calls("store", cases={cases})]
""")


def _on_function(cases: str) -> list:
    return _compile(f"""
def show(repo):
    __archtest__: Annotated[None, forbid_runtime_calls("store", cases={cases})]
""")


def _on_class(marker: str) -> list:
    return _compile(f"""
class Account:
    __archtest__: Annotated[None, {marker}]
""")


def _problem(rules: list) -> tuple[str, str] | None:
    sentinels = [rule for rule in rules if rule.rule_type == "compiler_invalid_param"]
    if not sentinels:
        return None
    return sentinels[0].params["param"], sentinels[0].params["compiler_reason"]


def test_steps_on_a_method_compile() -> None:
    rules = _on_method('[{"steps": [{"call": "add", "args": ["x"], "kwargs": {}}]}]')

    assert _problem(rules) is None
    assert rules[0].params["cases"][0]["steps"] == [
        {"call": "add", "args": ["x"], "kwargs": {}}
    ]


def test_steps_on_a_class_compile() -> None:
    rules = _on_class(
        'require_runtime_members("opened_at", cases=[{"steps": [{"call": "open"}]}])'
    )

    assert _problem(rules) is None


@pytest.mark.parametrize(
    ("cases", "reason"),
    [
        ('[{"steps": {"call": "add"}}]', "'steps' must be a list"),
        ('[{"steps": [{"args": []}]}]', "step 0 needs 'call'"),
        ('[{"steps": [{"call": ""}]}]', "step 0 needs 'call'"),
        ('[{"steps": [{"call": "add", "then": 1}]}]', "step 0 has unknown keys: then"),
        ('[{"steps": [{"call": "add", "args": {}}]}]', "step 0 'args' must be a list"),
        (
            '[{"steps": [{"call": "add", "kwargs": []}]}]',
            "step 0 'kwargs' must be a dict",
        ),
    ],
)
def test_malformed_steps_are_rejected(cases: str, reason: str) -> None:
    problem = _problem(_on_method(cases))

    assert problem is not None
    assert problem[0] == "cases"
    assert reason in problem[1]


def test_steps_on_a_function_are_rejected() -> None:
    problem = _problem(_on_function('[{"steps": [{"call": "add"}]}]'))

    assert problem == ("cases", "case 0 uses 'steps', which need an instance")


def test_steps_on_a_singleton_are_rejected() -> None:
    problem = _problem(
        _on_class(
            'is_runtime_singleton(cases=[{"steps": [{"call": "open"}]}], '
            'access="instance")'
        )
    )

    assert problem is not None
    assert "steps" in problem[1]


def test_a_spy_with_returns_compiles() -> None:
    rules = _on_function('[{"args": [{"$spy": "repo", "returns": {"find": 1}}]}]')

    assert _problem(rules) is None


@pytest.mark.parametrize(
    ("cases", "reason"),
    [
        ('[{"args": [{"$spy": "repo", "answer": 1}]}]', "unknown keys: answer"),
        ('[{"args": [{"$spy": "repo", "returns": [1]}]}]', "'returns' must be a dict"),
        ('[{"args": [{"$spy": ""}]}]', "a spy needs a name"),
    ],
)
def test_a_malformed_spy_is_rejected(cases: str, reason: str) -> None:
    problem = _problem(_on_function(cases))

    assert problem is not None
    assert problem[0] == "cases"
    assert reason in problem[1]
