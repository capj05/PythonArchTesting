from __future__ import annotations

from unittest.mock import Mock

import pytest

from pythonarchtesting.rules.compilation import compile_rules
from tests.unit.test_rules._dep001_helpers import build_source_index_from_rule_source


def test_dep001_compile_defaults_to_reachable_mode_and_v2_rule_id() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", "socket", scope="package", package="assignment"),
    ]
    return None
"""
    source_entity, _ = build_source_index_from_rule_source(source)
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["DEP001/forbid_imports/v2"]
    assert rules[0].rule_type == "import_policy"
    assert rules[0].params["forbidden"] == ["requests", "socket"]
    assert rules[0].params["mode"] == "reachable"
    assert rules[0].params["scope"] == "package"
    assert rules[0].params["package"] == "assignment"
    assert rules[0].params["fail_on_unmatched"] is False


def test_dep001_compile_honors_explicit_modes() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", mode="reachable"),
    ]
    __archtest__: Annotated[
        None,
        forbid_imports("socket", mode="direct"),
    ]
    return None
"""
    source_entity, _ = build_source_index_from_rule_source(source)
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "DEP001/forbid_imports/v2/d0",
        "DEP001/forbid_imports/v2/d1",
    ]
    assert [rule.params["mode"] for rule in rules] == ["reachable", "direct"]


def test_dep001_compile_normalizes_scope_values() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", scope="module"),
    ]
    __archtest__: Annotated[
        None,
        forbid_imports("socket", scope="entity"),
    ]
    __archtest__: Annotated[
        None,
        forbid_imports("subprocess", scope="nonsense"),
    ]
    return None
"""
    source_entity, _ = build_source_index_from_rule_source(source)
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.params["scope"] for rule in rules] == ["module", "module", "package"]


def test_dep001_compile_invalid_raw_mode_emits_compiler_error_evidence() -> None:
    source = """
from typing import Annotated

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        ("forbid_imports", {"forbidden": ["requests"], "mode": "invalid"}),
    ]
    return None
"""
    source_entity, _ = build_source_index_from_rule_source(source)
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_import_policy_mode"]
    assert evidence[0].payload["issue"] == "invalid_mode"
    assert evidence[0].payload["severity"] == "error"


def test_dep001_helper_rejects_invalid_mode() -> None:
    from pythonarchtesting.rules import forbid_imports

    with pytest.raises(
        ValueError,
        match="forbid_imports\\(\\) mode must be 'reachable' or 'direct'\\.",
    ):
        forbid_imports("requests", mode="invalid")
