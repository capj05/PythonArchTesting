from __future__ import annotations

from unittest.mock import Mock

from pythonarchtesting.rules import (
    is_abstract_class,
    is_concrete_class,
    is_final_class,
)
from pythonarchtesting.rules.compilation import compile_rules
from tests.unit.test_rules.protocol_rule_test_helpers import extract_entity


def test_mod001_import_surface_exposes_python_modifier_markers() -> None:
    abstract_marker = is_abstract_class()
    concrete_marker = is_concrete_class(severity="warning")
    final_marker = is_final_class(message="final required")

    assert abstract_marker.kind == "is_abstract_class"
    assert concrete_marker.kind == "is_concrete_class"
    assert concrete_marker.params["severity"] == "warning"
    assert final_marker.kind == "is_final_class"
    assert final_marker.message == "final required"


def test_mod001_is_abstract_class_compiles() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_class

class Contract:
    __archtest__: Annotated[None, is_abstract_class()]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")

    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["MOD001/is_abstract_class/v1"]
    assert rules[0].rule_type == "python_modifier"
    assert rules[0].params == {
        "modifier_kind": "abstract_class",
        "modifier_polarity": "positive",
        "fail_on_unmatched": True,
    }


def test_mod001_is_concrete_class_compiles() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_concrete_class

class Contract:
    __archtest__: Annotated[None, is_concrete_class()]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")

    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["MOD001/is_concrete_class/v1"]
    assert rules[0].rule_type == "python_modifier"
    assert rules[0].params == {
        "modifier_kind": "concrete_class",
        "modifier_polarity": "positive",
        "fail_on_unmatched": True,
    }


def test_mod001_is_final_class_compiles() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_final_class

class Contract:
    __archtest__: Annotated[None, is_final_class()]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")

    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["MOD001/is_final_class/v1"]
    assert rules[0].rule_type == "python_modifier"
    assert rules[0].params == {
        "modifier_kind": "final_class",
        "modifier_polarity": "positive",
        "fail_on_unmatched": True,
    }


def test_mod001_non_class_placement_emits_invalid_target() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_class

def helper() -> None:
    __archtest__: Annotated[None, is_abstract_class()]
"""
    source_entity = extract_entity(
        source, role="source", kind="function", name="helper"
    )

    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
