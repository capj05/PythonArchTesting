from __future__ import annotations

from unittest.mock import Mock

from pythonarchtesting.rules import require_method_set
from pythonarchtesting.rules.compilation import compile_rules
from tests.unit.test_rules.protocol_rule_test_helpers import (
    extract_entities,
    extract_entity,
)


def test_api005_import_surface_exposes_require_method_set() -> None:
    marker = require_method_set(name_match="names", names=["setUp", "tearDown"])

    assert marker.kind == "require_method_set"
    assert marker.params["names"] == ["setUp", "tearDown"]


def test_api005_class_level_declaration_compiles() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class TestContract:
    __archtest__: Annotated[
        None,
        require_method_set(
            name_match="regex",
            pattern=r"test_.*",
            declared_only=True,
            method_kind="instance",
            min_count=1,
            max_count=3,
        ),
    ]
"""
    source_entity = extract_entity(
        source, role="source", kind="class", name="TestContract"
    )
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API005/require_method_set/v1"]
    assert [rule.rule_type for rule in rules] == ["method_set"]
    assert rules[0].params == {
        "name_match": "regex",
        "names": None,
        "pattern": r"test_.*",
        "declared_only": True,
        "method_kind": "instance",
        "min_count": 1,
        "max_count": 3,
        "fail_on_unmatched": True,
    }


def test_api005_non_class_placement_emits_invalid_target() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

def helper() -> None:
    __archtest__: Annotated[None, require_method_set()]
"""
    source_entity = extract_entity(
        source, role="source", kind="function", name="helper"
    )
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


def test_api005_invalid_name_match_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class Contract:
    __archtest__: Annotated[None, require_method_set(name_match="alias")]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api005_regex_without_pattern_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class Contract:
    __archtest__: Annotated[None, require_method_set(name_match="regex")]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api005_names_without_names_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class Contract:
    __archtest__: Annotated[None, require_method_set(name_match="names")]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api005_negative_min_count_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class Contract:
    __archtest__: Annotated[None, require_method_set(min_count=-1)]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api005_negative_max_count_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class Contract:
    __archtest__: Annotated[None, require_method_set(max_count=-1)]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api005_max_count_less_than_min_count_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class Contract:
    __archtest__: Annotated[None, require_method_set(min_count=2, max_count=1)]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api005_multiple_rules_get_suffixed_rule_ids() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_method_set

class Contract:
    __archtest__: Annotated[None, require_method_set(name_match="regex", pattern=r"test_.*")]
    __archtest__: Annotated[
        None,
        require_method_set(name_match="names", names=["setUp", "tearDown"], min_count=2),
    ]
"""
    source_entities = extract_entities(source, role="source")
    source_class = next(entity for entity in source_entities if entity.kind == "class")
    rules, evidence, compiler_results = compile_rules([source_class], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == [
        "API005/require_method_set/v1/d0",
        "API005/require_method_set/v1/d1",
    ]
