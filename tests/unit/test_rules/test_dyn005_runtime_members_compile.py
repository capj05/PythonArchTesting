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
from pythonarchtesting.rules import forbid_runtime_members, require_runtime_members

class Settings:
    __archtest__: Annotated[None, {marker}]
""")


@pytest.mark.parametrize(
    ("marker", "mode"),
    [("require_runtime_members", "require"), ("forbid_runtime_members", "forbid")],
)
def test_member_markers_compile_to_a_runtime_members_rule(
    marker: str, mode: str
) -> None:
    rules, evidence, compiler_results = _on_class(
        f'{marker}("port", "host", "port", cases=[{{"args": [{{}}]}}], '
        'timeout_s=2, severity="warning")'
    )

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [f"DYN005/{marker}/v1"]
    rule = rules[0]
    assert rule.rule_type == "runtime_members"
    assert rule.evidence_type == "runtime"
    assert rule.scope == "class"
    assert rule.severity == "warning"
    assert rule.params["mode"] == mode
    assert rule.params["names"] == ["host", "port"]
    assert rule.params["cases"] == [{"args": [{}]}]
    assert rule.params["timeout_s"] == 2.0
    assert rule.params["fail_on_unmatched"] is True
    assert "--dynamic" in rule.fix_hints[-1]


@pytest.mark.parametrize(
    "marker", ["require_runtime_members", "forbid_runtime_members"]
)
def test_a_method_is_not_a_valid_target(marker: str) -> None:
    rules, evidence, _ = _compile(f"""
from typing import Annotated
from pythonarchtesting.rules import {marker}

class Settings:
    def load(self):
        __archtest__: Annotated[None, {marker}("port", cases=[{{}}])]
""")

    assert rules == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
    assert evidence[0].payload["expected_kind"] == "class"
    assert evidence[0].payload["found_kind"] == "method"


@pytest.mark.parametrize(
    ("marker", "param", "reason"),
    [
        ("require_runtime_members(cases=[{}])", "names", "at least one attribute"),
        ('require_runtime_members("", cases=[{}])', "names", "at least one attribute"),
        (
            'forbid_runtime_members("not-a-name", cases=[{}])',
            "names",
            "at least one attribute",
        ),
        ('require_runtime_members("port", cases=[])', "cases", "non-empty list"),
        (
            'forbid_runtime_members("port", types={"port": "int"}, cases=[{}])',
            "types",
            "types does not apply to forbid_runtime_members",
        ),
        (
            'require_runtime_members("port", types={"host": "str"}, cases=[{}])',
            "types",
            "types names members not listed: host",
        ),
        (
            'require_runtime_members("port", types={"port": 1}, cases=[{}])',
            "types",
            "types must map member names to class names",
        ),
        (
            'require_runtime_members("port", cases=[{"expect": 1}])',
            "cases",
            "unknown keys: expect",
        ),
        (
            'forbid_runtime_members("port", cases=[{"init": {}}])',
            "cases",
            "only methods support",
        ),
        (
            'require_runtime_members("port", cases=[{}], init={"args": []})',
            "init",
            "only applies to methods",
        ),
        (
            'require_runtime_members("port", cases=[{}], timeout_s=0)',
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
    assert rules[0].rule_id.startswith("DYN005/")
    assert [item.type for item in evidence] == ["compiler_invalid_param"]


def test_types_reach_the_rule_only_when_given() -> None:
    typed, evidence, _ = _on_class(
        'require_runtime_members("repo", types={"repo": "repository.Repo"}, '
        "cases=[{}])"
    )
    plain, _, _ = _on_class('require_runtime_members("repo", cases=[{}])')

    assert evidence == []
    assert typed[0].params["types"] == {"repo": "repository.Repo"}
    assert "types" not in plain[0].params
