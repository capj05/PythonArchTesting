from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest

from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.rules.compilation import compile_rules


def _compile(source: str) -> tuple[list, list, list]:
    entities = extract_entities_from_source(
        textwrap.dedent(source).strip() + "\n",
        Path("source_module.py"),
        Path("."),
        None,
        role="source",
        include_nested_functions=False,
        root_label="source",
    )
    return compile_rules(entities, Mock())


def _on_class(marker: str) -> tuple[list, list, list]:
    return _compile(f"""
from typing import Annotated
from pythonarchtesting.rules import is_runtime_abstract_class, is_runtime_concrete_class

class Inventory:
    __archtest__: Annotated[None, {marker}]
""")


def test_concrete_class_compiles_to_a_class_kind_rule() -> None:
    rules, evidence, _ = _on_class(
        'is_runtime_concrete_class(cases=[{"args": [1], "kwargs": {"a": 2}}])'
    )

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN006/is_runtime_concrete_class/v1"]
    rule = rules[0]
    assert rule.rule_type == "runtime_class_kind"
    assert rule.scope == "class"
    assert rule.params["expect"] == "concrete"
    assert rule.params["cases"] == [{"args": [1], "kwargs": {"a": 2}}]
    assert rule.params["timeout_s"] == 5.0


def test_abstract_class_compiles_with_one_empty_case_and_no_init() -> None:
    rules, evidence, _ = _on_class("is_runtime_abstract_class(timeout_s=3)")

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN006/is_runtime_abstract_class/v1"]
    rule = rules[0]
    assert rule.rule_type == "runtime_class_kind"
    assert rule.params["expect"] == "abstract"
    assert rule.params["cases"] == [{}]
    assert rule.params["init"] is None
    assert rule.params["timeout_s"] == 3.0
    assert rule.params["fail_on_unmatched"] is True


@pytest.mark.parametrize(
    "marker",
    ["is_runtime_concrete_class(cases=[{}])", "is_runtime_abstract_class()"],
)
def test_a_function_is_not_a_valid_target(marker: str) -> None:
    name = marker.split("(")[0]
    rules, evidence, _ = _compile(f"""
from typing import Annotated
from pythonarchtesting.rules import {name}

def build():
    __archtest__: Annotated[None, {marker}]
""")

    # The misplaced marker is a FAILED sentinel, not missing from the report.
    assert [(rule.rule_type, rule.params["param"]) for rule in rules] == [
        ("compiler_invalid_param", "target_kind")
    ]
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
    assert evidence[0].payload["expected_kind"] == "class"


@pytest.mark.parametrize(
    ("marker", "param", "reason"),
    [
        ("is_runtime_concrete_class(cases=[])", "cases", "non-empty list"),
        (
            'is_runtime_concrete_class(cases=[{"result": 1}])',
            "cases",
            "unknown keys: result",
        ),
        (
            'is_runtime_concrete_class(cases=[{"args": "x"}])',
            "cases",
            "'args' must be a list",
        ),
        (
            "is_runtime_abstract_class(cases=[{}])",
            "cases",
            "takes no cases",
        ),
        (
            'is_runtime_abstract_class(timeout_s="slow")',
            "timeout_s",
            "timeout_s must be a number",
        ),
        (
            "is_runtime_abstract_class(timeout_s=True)",
            "timeout_s",
            "timeout_s must be a number",
        ),
    ],
)
def test_invalid_params_compile_to_a_sentinel(
    marker: str, param: str, reason: str
) -> None:
    rules, evidence, _ = _on_class(marker)

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert rules[0].params["param"] == param
    assert reason in rules[0].params["compiler_reason"]
    assert rules[0].rule_id.startswith(f"DYN006/{marker.split('(')[0]}/")
    assert [item.type for item in evidence] == ["compiler_invalid_param"]
