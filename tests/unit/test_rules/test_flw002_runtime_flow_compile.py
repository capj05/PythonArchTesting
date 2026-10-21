from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest

from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.rules.compilation import compile_rules

_TEMPLATE = """
from typing import Annotated
from pythonarchtesting.rules import enforce_flow, flow


def clean(raw: str) -> str:
    text = raw
    __archtest__: Annotated[None, flow("raw", variable="text")]
    text = (
        text.strip()
    )
    __archtest__: Annotated[None, flow("stripped", variable="text")]
    __archtest__: Annotated[None, {marker}]
    return text
"""


_METHOD_TEMPLATE = """
from typing import Annotated
from pythonarchtesting.rules import enforce_flow, flow


class Cleaner:
    def __init__(self, suffix: str) -> None:
        self.suffix = suffix

    def clean(self, raw: str) -> str:
        text = raw + self.suffix
        __archtest__: Annotated[None, flow("raw", variable="text")]
        __archtest__: Annotated[None, {marker}]
        return text
"""


def _compile(marker: str, template: str = _TEMPLATE) -> tuple[list, list, list]:
    source = template.replace("{marker}", marker)
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


def test_without_cases_enforce_flow_stays_static() -> None:
    rules, _, _ = _compile('enforce_flow(["raw", "stripped"])')

    assert [rule.rule_id for rule in rules] == ["FLW001/enforce_flow/v1"]
    assert rules[0].evidence_type == "static"


def test_with_cases_enforce_flow_compiles_to_a_runtime_rule() -> None:
    rules, evidence, _ = _compile(
        'enforce_flow(["raw", "stripped"], cases=[{"args": [" a "]}], timeout_s=2)'
    )

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["FLW002/enforce_flow_runtime/v1"]
    rule = rules[0]
    assert rule.rule_type == "runtime_flow"
    assert rule.evidence_type == "runtime"
    assert rule.params["variable"] == "text"
    assert rule.params["timeout_s"] == 2.0
    assert rule.params["init"] is None
    # Line numbers are 1-based in the dedented source: "text = raw" is line 6,
    # the multi-line strip spans lines 8-10 up to the marker on line 11.
    assert rule.params["spans"] == [
        {"stage": "raw", "start": 6, "end": 6, "variable": "text"},
        {"stage": "stripped", "start": 8, "end": 10, "variable": "text"},
    ]


def test_runtime_spans_cover_only_declared_stages() -> None:
    rules, _, _ = _compile('enforce_flow(["stripped"], cases=[{"args": ["a"]}])')

    assert [span["stage"] for span in rules[0].params["spans"]] == ["stripped"]


@pytest.mark.parametrize(
    ("cases", "fragment"),
    [
        ("[]", "non-empty list"),
        ('[{"args": ["a"], "returns": "a"}]', "only give call arguments"),
        ('[{"init": {}}]', "only methods support"),
        ('[{"args": "a"}]', "'args' must be a list"),
    ],
)
def test_invalid_runtime_cases_produce_a_sentinel(cases: str, fragment: str) -> None:
    rules, evidence, _ = _compile(f'enforce_flow(["raw"], cases={cases})')

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert fragment in rules[0].params["compiler_reason"]
    assert [item.type for item in evidence] == ["compiler_invalid_flow_declaration"]


def test_init_on_a_method_is_carried_to_the_rule() -> None:
    rules, _, _ = _compile(
        'enforce_flow(["raw"], cases=[{"args": ["a"]}], init={"args": ["!"]})',
        _METHOD_TEMPLATE,
    )

    assert [rule.rule_id for rule in rules] == ["FLW002/enforce_flow_runtime/v1"]
    assert rules[0].params["init"] == {"args": ["!"]}


@pytest.mark.parametrize(
    ("init", "template", "fragment"),
    [
        ('{"args": ["!"]}', _TEMPLATE, "init only applies to methods"),
        ('{"args": "!"}', _METHOD_TEMPLATE, "init['args'] must be a list"),
    ],
)
def test_invalid_init_produces_a_sentinel(
    init: str, template: str, fragment: str
) -> None:
    rules, _, _ = _compile(
        f'enforce_flow(["raw"], cases=[{{"args": ["a"]}}], init={init})', template
    )

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert fragment in rules[0].params["compiler_reason"]
