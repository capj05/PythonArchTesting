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


def _on_function(marker: str) -> tuple[list, list, list]:
    return _compile(f"""
from typing import Annotated
from pythonarchtesting.rules import enforce_reference_calls

def handle(request):
    __archtest__: Annotated[None, {marker}]
""")


def test_enforce_reference_calls_compiles_to_a_reference_calls_rule() -> None:
    rules, evidence, compiler_results = _on_function(
        'enforce_reference_calls(cases=[{"args": [1]}], timeout_s=2, '
        'severity="warning")'
    )

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["DYN001/enforce_reference_calls/v1"]
    rule = rules[0]
    assert rule.rule_type == "runtime_reference_calls"
    assert rule.evidence_type == "runtime"
    assert rule.severity == "warning"
    assert rule.params["cases"] == [{"args": [1]}]
    assert rule.params["require_all"] is False
    assert rule.params["init"] is None
    assert rule.params["timeout_s"] == 2.0


def test_require_all_is_carried_into_the_rule() -> None:
    rules, _, _ = _on_function("enforce_reference_calls(cases=[{}], require_all=True)")

    assert rules[0].params["require_all"] is True


def test_allow_new_modules_is_carried_only_when_set() -> None:
    allowed, _, _ = _on_function(
        "enforce_reference_calls(cases=[{}], allow_new_modules=True)"
    )
    plain, _, _ = _on_function("enforce_reference_calls(cases=[{}])")

    assert allowed[0].params["allow_new_modules"] is True
    assert "allow_new_modules" not in plain[0].params


def test_a_method_accepts_an_init() -> None:
    rules, evidence, _ = _compile("""
from typing import Annotated
from pythonarchtesting.rules import enforce_reference_calls

class Controller:
    def handle(self, request):
        __archtest__: Annotated[
            None, enforce_reference_calls(init={"args": [1]}, cases=[{"args": [2]}])
        ]
""")

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN001/enforce_reference_calls/v1"]
    assert rules[0].params["init"] == {"args": [1]}


def test_a_module_is_not_a_valid_target() -> None:
    rules, evidence, _ = _compile("""
from typing import Annotated
from pythonarchtesting.rules import enforce_reference_calls

__archtest__: Annotated[None, enforce_reference_calls(cases=[{}])]
""")

    assert rules == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


@pytest.mark.parametrize(
    ("marker", "param", "reason"),
    [
        (
            'enforce_reference_calls(cases=[{}], require_all="yes")',
            "require_all",
            "require_all must be True or False",
        ),
        (
            "enforce_reference_calls(cases=[{}], allow_new_modules=1)",
            "allow_new_modules",
            "allow_new_modules must be True or False",
        ),
        ("enforce_reference_calls(cases=[])", "cases", "non-empty list"),
        ("enforce_reference_calls()", "cases", "non-empty list"),
        (
            'enforce_reference_calls(cases=[{"args": [1], "returns": 2}])',
            "cases",
            "unknown keys: returns",
        ),
        (
            "enforce_reference_calls(cases=[{}], timeout_s=0)",
            "timeout_s",
            "timeout_s must be a number",
        ),
    ],
)
def test_invalid_params_compile_to_a_sentinel(
    marker: str, param: str, reason: str
) -> None:
    rules, evidence, _ = _on_function(marker)

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert rules[0].params["param"] == param
    assert reason in rules[0].params["compiler_reason"]
    assert rules[0].rule_id.startswith("DYN001/enforce_reference_calls/")
    assert [item.type for item in evidence] == ["compiler_invalid_param"]
