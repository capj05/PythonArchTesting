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


def _on_method(marker: str) -> tuple[list, list, list]:
    return _compile(f"""
from typing import Annotated
from pythonarchtesting.rules import forbid_runtime_instantiation

class Service:
    def handle(self, request):
        __archtest__: Annotated[None, {marker}]
""")


def test_forbid_runtime_instantiation_compiles_to_a_runtime_instances_rule() -> None:
    rules, evidence, compiler_results = _on_method(
        'forbid_runtime_instantiation("repository", "notifier", "repository", '
        'allow=["repository.fake"], init={"args": [1]}, cases=[{"args": [2]}])'
    )

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "DYN004/forbid_runtime_instantiation/v1"
    ]
    rule = rules[0]
    assert rule.rule_type == "runtime_instances"
    assert rule.evidence_type == "runtime"
    assert rule.params["mode"] == "forbid"
    assert rule.params["modules"] == ["notifier", "repository"]
    assert rule.params["allow"] == ["repository.fake"]
    assert rule.params["init"] == {"args": [1]}
    assert rule.params["timeout_s"] == 5.0


def test_explicit_none_for_allow_is_an_empty_allow_list() -> None:
    rules, evidence, _ = _on_method(
        'forbid_runtime_instantiation("repository", allow=None, cases=[{}])'
    )

    assert evidence == []
    assert rules[0].params["allow"] == []


def test_a_class_is_not_a_valid_target() -> None:
    rules, evidence, _ = _compile("""
from typing import Annotated
from pythonarchtesting.rules import forbid_runtime_instantiation

class Service:
    __archtest__: Annotated[None, forbid_runtime_instantiation("db", cases=[{}])]
""")

    assert rules == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


@pytest.mark.parametrize(
    ("marker", "param", "reason"),
    [
        ("forbid_runtime_instantiation(cases=[{}])", "modules", "at least one module"),
        (
            'forbid_runtime_instantiation("db", allow="db.fake", cases=[{}])',
            "allow",
            "allow must be a list of module names",
        ),
        (
            'forbid_runtime_instantiation("db", allow=[""], cases=[{}])',
            "allow",
            "allow must be a list of module names",
        ),
        ('forbid_runtime_instantiation("db", cases=[])', "cases", "non-empty list"),
        (
            'forbid_runtime_instantiation("db", cases=[{"expect": 1}])',
            "cases",
            "unknown keys: expect",
        ),
        (
            'forbid_runtime_instantiation("db", init=[1], cases=[{}])',
            "init",
            "init must be a dict",
        ),
    ],
)
def test_invalid_params_compile_to_a_sentinel(
    marker: str, param: str, reason: str
) -> None:
    rules, evidence, _ = _on_method(marker)

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert rules[0].params["param"] == param
    assert reason in rules[0].params["compiler_reason"]
    assert rules[0].rule_id.startswith("DYN004/forbid_runtime_instantiation/")
    assert [item.type for item in evidence] == ["compiler_invalid_param"]
