from __future__ import annotations

from typing import Any
from unittest.mock import Mock

from pythonarchtesting.rules import require_member_set
from pythonarchtesting.rules.compilation import compile_rules
from tests.unit.test_rules.protocol_rule_test_helpers import (
    extract_entities,
    extract_entity,
)


def _assert_sentinel(rules: list[Any], *, param: str) -> None:
    """Assert the compiler emitted exactly one API006 invalid-param sentinel."""
    assert len(rules) == 1
    sentinel = rules[0]
    assert sentinel.rule_type == "compiler_invalid_param"
    assert sentinel.name == "require_member_set"
    assert sentinel.rule_id.startswith(
        f"API006/require_member_set/invalid_declaration/{param}"
    )
    assert sentinel.params["decorator"] == "require_member_set"
    assert sentinel.params["param"] == param


def test_api006_import_surface_exposes_require_member_set() -> None:
    marker = require_member_set(
        member_kinds=("attribute", "property"), name_match="names", names=["x", "y"]
    )

    assert marker.kind == "require_member_set"
    assert marker.params["member_kinds"] == ["attribute", "property"]
    assert marker.params["names"] == ["x", "y"]


def test_api006_class_level_declaration_compiles() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[
        None,
        require_member_set(
            member_kinds=("method", "attribute"),
            name_match="regex",
            pattern=r"data_.*",
            declared_only=True,
            method_kind="instance",
            storage="instance",
            min_count=1,
            max_count=3,
        ),
    ]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API006/require_member_set/v1"]
    assert [rule.rule_type for rule in rules] == ["member_set"]
    assert rules[0].params == {
        "member_kinds": ["method", "attribute"],
        "name_match": "regex",
        "names": None,
        "pattern": r"data_.*",
        "declared_only": True,
        "method_kind": "instance",
        "storage": "instance",
        "allow_property": True,
        "descriptor_kinds": None,
        "include_dynamic_attributes": False,
        "interpret_dataclass_fields": False,
        "constructor_kind": "auto",
        "include_dataclass_constructor": True,
        "min_count": 1,
        "max_count": 3,
        "fail_on_unmatched": True,
    }


def test_api006_default_params_compile_with_any_member_kinds() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[None, require_member_set()]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API006/require_member_set/v1"]
    assert rules[0].params["member_kinds"] == ["any"]
    assert rules[0].params["name_match"] == "any"
    assert rules[0].params["min_count"] == 1
    assert rules[0].params["max_count"] is None


def test_api006_non_class_placement_emits_invalid_target() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

def helper() -> None:
    __archtest__: Annotated[None, require_member_set()]
"""
    source_entity = extract_entity(
        source, role="source", kind="function", name="helper"
    )
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="target_kind")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


def test_api006_invalid_member_kind_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[None, require_member_set(member_kinds=("bogus",))]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="member_kinds")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api006_any_combined_with_other_kinds_is_invalid() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[
        None, require_member_set(member_kinds=("any", "method"))
    ]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="member_kinds")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api006_invalid_name_match_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[None, require_member_set(name_match="alias")]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="name_match")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api006_regex_without_pattern_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[None, require_member_set(name_match="regex")]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="pattern")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api006_names_without_names_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[None, require_member_set(name_match="names")]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="names")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api006_invalid_method_kind_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[None, require_member_set(method_kind="abstract")]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="method_kind")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api006_invalid_storage_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[None, require_member_set(storage="bogus")]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="storage")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api006_invalid_descriptor_kinds_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[
        None, require_member_set(descriptor_kinds=("staticmethod",))
    ]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="descriptor_kinds")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api006_invalid_constructor_kind_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[None, require_member_set(constructor_kind="__call__")]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="constructor_kind")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api006_negative_min_count_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[None, require_member_set(min_count=-1)]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="min_count")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api006_max_count_less_than_min_count_emits_invalid_declaration() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[
        None, require_member_set(min_count=2, max_count=1)
    ]
"""
    source_entity = extract_entity(source, role="source", kind="class", name="Contract")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    _assert_sentinel(rules, param="max_count")
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_api006_multiple_rules_get_suffixed_rule_ids() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import require_member_set

class Contract:
    __archtest__: Annotated[
        None,
        require_member_set(member_kinds=("method",), name_match="regex", pattern=r"f_.*"),
    ]
    __archtest__: Annotated[
        None,
        require_member_set(member_kinds=("attribute",), min_count=2),
    ]
"""
    source_entities = extract_entities(source, role="source")
    source_class = next(entity for entity in source_entities if entity.kind == "class")
    rules, evidence, compiler_results = compile_rules([source_class], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == [
        "API006/require_member_set/v1/d0",
        "API006/require_member_set/v1/d1",
    ]
