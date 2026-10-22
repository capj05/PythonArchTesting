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
from pythonarchtesting.rules import forbid_runtime_calls, require_runtime_calls

def handle(request, service):
    __archtest__: Annotated[None, {marker}]
""")


def test_forbid_runtime_calls_compiles_to_a_runtime_calls_rule() -> None:
    rules, evidence, compiler_results = _on_function(
        'forbid_runtime_calls("repository", "sqlite3", "repository", '
        'allow=["sqlite3.dbapi2"], cases=[{"args": [1, {"$new": "service.S"}]}], '
        "timeout_s=2)"
    )

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["DYN001/forbid_runtime_calls/v1"]
    rule = rules[0]
    assert rule.rule_type == "runtime_calls"
    assert rule.evidence_type == "runtime"
    assert rule.params["mode"] == "forbid"
    assert rule.params["modules"] == ["repository", "sqlite3"]
    assert rule.params["allow"] == ["sqlite3.dbapi2"]
    assert rule.params["cases"] == [{"args": [1, {"$new": "service.S"}]}]
    assert rule.params["init"] is None
    assert rule.params["timeout_s"] == 2.0


def test_transitive_and_through_reach_the_rule() -> None:
    rules, evidence, _ = _on_function(
        'forbid_runtime_calls("repository", transitive=True, through=["service"], '
        "cases=[{}])"
    )

    assert evidence == []
    assert rules[0].params["transitive"] is True
    assert rules[0].params["through"] == ["service"]


def test_without_transitive_the_rule_has_no_such_params() -> None:
    rules, _, _ = _on_function('forbid_runtime_calls("repository", cases=[{}])')

    assert "transitive" not in rules[0].params
    assert "through" not in rules[0].params


def test_require_runtime_calls_compiles_in_require_mode() -> None:
    rules, evidence, _ = _on_function(
        'require_runtime_calls("service", cases=[{"args": [1, 2]}])'
    )

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN001/require_runtime_calls/v1"]
    assert rules[0].rule_type == "runtime_calls"
    assert rules[0].params["mode"] == "require"
    assert rules[0].params["modules"] == ["service"]
    assert rules[0].params["allow"] == []
    assert rules[0].params["timeout_s"] == 5.0


def test_a_method_accepts_a_shared_and_a_per_case_init() -> None:
    rules, evidence, _ = _compile("""
from typing import Annotated
from pythonarchtesting.rules import forbid_runtime_calls

class Controller:
    def handle(self, request):
        __archtest__: Annotated[
            None,
            forbid_runtime_calls(
                "repository",
                init={"args": [1]},
                cases=[{"args": [2]}, {"init": {"kwargs": {"x": 1}}, "args": [3]}],
            ),
        ]
""")

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN001/forbid_runtime_calls/v1"]
    assert rules[0].params["init"] == {"args": [1]}


def test_a_module_is_not_a_valid_target() -> None:
    rules, evidence, _ = _compile("""
from typing import Annotated
from pythonarchtesting.rules import forbid_runtime_calls

__archtest__: Annotated[None, forbid_runtime_calls("db", cases=[{}])]
""")

    assert rules == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


@pytest.mark.parametrize(
    ("marker", "param", "reason"),
    [
        ("forbid_runtime_calls(cases=[{}])", "modules", "at least one module"),
        ("require_runtime_calls(cases=[{}])", "modules", "at least one module"),
        (
            'require_runtime_calls("service", allow=["service.x"], cases=[{}])',
            "allow",
            "allow does not apply to require_runtime_calls",
        ),
        (
            'forbid_runtime_calls("db", through=["service"], cases=[{}])',
            "through",
            "only with transitive=True",
        ),
        (
            'forbid_runtime_calls("db", transitive="yes", cases=[{}])',
            "transitive",
            "True or False",
        ),
        (
            'require_runtime_calls("db", transitive=True, cases=[{}])',
            "transitive",
            "transitive does not apply to require_runtime_calls",
        ),
        (
            'forbid_runtime_calls("db", transitive=True, through="service", cases=[{}])',
            "through",
            "list of module names",
        ),
        ('forbid_runtime_calls("db", cases=[])', "cases", "non-empty list"),
        (
            'forbid_runtime_calls("db", cases=[{"args": [1], "returns": 2}])',
            "cases",
            "unknown keys: returns",
        ),
        (
            'forbid_runtime_calls("db", cases=[{"raises": "ValueError"}])',
            "cases",
            "only give call arguments",
        ),
        ('forbid_runtime_calls("db", cases=[{"args": 1}])', "cases", "must be a list"),
        (
            'forbid_runtime_calls("db", cases=[{"init": {"args": []}}])',
            "cases",
            "only methods support",
        ),
        (
            'forbid_runtime_calls("db", init={"args": []}, cases=[{}])',
            "init",
            "only applies to methods",
        ),
        (
            'forbid_runtime_calls("db", cases=[{}], timeout_s=0)',
            "timeout_s",
            "timeout_s must be a number",
        ),
        (
            'forbid_runtime_calls("db", cases=[{}], timeout_s=600)',
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
    assert rules[0].rule_id.startswith("DYN001/")
    assert [item.type for item in evidence] == ["compiler_invalid_param"]


def test_invalid_init_on_a_method_is_rejected() -> None:
    rules, _, _ = _compile("""
from typing import Annotated
from pythonarchtesting.rules import require_runtime_calls

class Controller:
    def handle(self):
        __archtest__: Annotated[
            None,
            require_runtime_calls("service", init={"extra": 1}, cases=[{}]),
        ]
""")

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert rules[0].params["param"] == "init"
    assert "unknown keys: extra" in rules[0].params["compiler_reason"]


def test_explicit_none_for_the_optional_params_is_accepted() -> None:
    rules, evidence, _ = _on_function(
        'forbid_runtime_calls("db", allow=None, init=None, cases=[{}])'
    )

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN001/forbid_runtime_calls/v1"]
    assert rules[0].params["allow"] == []
