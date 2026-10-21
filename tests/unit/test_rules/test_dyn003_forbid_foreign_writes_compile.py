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
from pythonarchtesting.rules import forbid_foreign_writes

def transfer(source, target, amount):
    __archtest__: Annotated[None, {marker}]
""")


def test_dyn003_compile_emits_a_runtime_writes_rule() -> None:
    rules, evidence, compiler_results = _on_function(
        'forbid_foreign_writes(cases=[{"args": [{"$new": "account.Account"}, '
        '{"$new": "account.Account"}, 1.0]}], timeout_s=3, severity="warning")'
    )

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["DYN003/forbid_foreign_writes/v1"]
    rule = rules[0]
    assert rule.rule_type == "runtime_writes"
    assert rule.evidence_type == "runtime"
    assert rule.severity == "warning"
    assert rule.params["timeout_s"] == 3.0
    assert rule.params["init"] is None
    assert len(rule.params["cases"]) == 1
    assert "mode" not in rule.params


def test_dyn003_compile_on_a_method_keeps_init() -> None:
    rules, evidence, _ = _compile("""
from typing import Annotated
from pythonarchtesting.rules import forbid_foreign_writes

class Teller:
    def pay(self, amount):
        __archtest__: Annotated[
            None,
            forbid_foreign_writes(init={"args": [1]}, cases=[{"args": [2]}]),
        ]
""")

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN003/forbid_foreign_writes/v1"]
    assert rules[0].params["init"] == {"args": [1]}


def test_dyn003_compile_on_a_class_emits_invalid_target_evidence() -> None:
    rules, evidence, _ = _compile("""
from typing import Annotated
from pythonarchtesting.rules import forbid_foreign_writes

class Account:
    __archtest__: Annotated[None, forbid_foreign_writes(cases=[{}])]
""")

    assert rules == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


@pytest.mark.parametrize(
    ("marker", "param", "reason"),
    [
        ("forbid_foreign_writes(cases=[])", "cases", "non-empty list"),
        (
            'forbid_foreign_writes(cases=[{"args": [1], "state": {"x": 1}}])',
            "cases",
            "unknown keys: state",
        ),
        (
            'forbid_foreign_writes(cases=[{"trace": {"x": [1]}}])',
            "cases",
            "only give call arguments",
        ),
        (
            'forbid_foreign_writes(init={"args": [1]}, cases=[{}])',
            "init",
            "only applies to methods",
        ),
        ("forbid_foreign_writes(cases=[{}], timeout_s=-1)", "timeout_s", "(0, 60]"),
    ],
)
def test_dyn003_compile_rejects_invalid_params_with_a_sentinel(
    marker: str, param: str, reason: str
) -> None:
    rules, evidence, _ = _on_function(marker)

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert rules[0].rule_id.startswith("DYN003/forbid_foreign_writes/")
    assert rules[0].params["param"] == param
    assert reason in rules[0].params["compiler_reason"]
    assert [item.type for item in evidence] == ["compiler_invalid_param"]
