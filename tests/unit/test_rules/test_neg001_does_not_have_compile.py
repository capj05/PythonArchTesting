from __future__ import annotations

from unittest.mock import Mock

from pythonarchtesting.entities import build_canonical_id
from pythonarchtesting.rules.compilation import compile_rules
from tests.unit.test_rules.protocol_rule_test_helpers import extract_entities


def test_neg001_compile_emits_member_absence_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have(
            "password",
            member_kind="attribute",
            storage="instance",
            declared_only=True,
        ),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["NEG001/does_not_have/v1"]
    assert [rule.rule_type for rule in rules] == ["member_absence"]
    assert rules[0].params == {
        "name": "password",
        "member_kind": "attribute",
        "storage": "instance",
        "declared_only": True,
        "fail_on_unmatched": False,
    }


def test_neg001_compile_non_class_emits_invalid_target_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

def build() -> None:
    __archtest__: Annotated[None, does_not_have("password")]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
    assert evidence[0].payload["issue"] == "compiler_invalid_target"


def test_neg001_compile_invalid_member_kind_emits_compiler_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have("password", member_kind="field"),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == [
        "compiler_invalid_member_absence_declaration"
    ]
    assert evidence[0].payload["issue"] == "invalid_member_kind"


def test_neg001_compile_invalid_storage_emits_compiler_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have("password", member_kind="attribute", storage="slot"),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == [
        "compiler_invalid_member_absence_declaration"
    ]
    assert evidence[0].payload["issue"] == "invalid_storage"


def test_neg001_compile_rejects_method_storage_combination() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have("debug_dump", member_kind="method", storage="class"),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == [
        "compiler_invalid_member_absence_declaration"
    ]
    assert evidence[0].payload["issue"] == "invalid_storage_for_member_kind"


def test_neg001_compile_rejects_property_storage_combination() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have("email", member_kind="property", storage="instance"),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == [
        "compiler_invalid_member_absence_declaration"
    ]
    assert evidence[0].payload["issue"] == "invalid_storage_for_member_kind"


def test_neg001_signature_annotation_usage_is_rejected_in_v1() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

def build(user: Annotated[object, does_not_have("password")]) -> None:
    return None
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]


def test_neg001_compile_emits_v2_alias_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have(
            member_kind="method",
            name_match="alias",
            aliases=["debug_dump", "trace_dump"],
        ),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["NEG001/does_not_have/v2"]
    assert rules[0].params["name_match"] == "alias"
    assert rules[0].params["aliases"] == ["debug_dump", "trace_dump"]


def test_neg001_compile_emits_v2_regex_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have(
            member_kind="method",
            name_match="regex",
            pattern="debug_.+",
        ),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["NEG001/does_not_have/v2"]
    assert rules[0].params["pattern"] == "debug_.+"


def test_neg001_compile_rejects_alias_name_match_without_aliases() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have(member_kind="method", name_match="alias"),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == [
        "compiler_invalid_member_absence_declaration"
    ]
    assert evidence[0].payload["issue"] == "missing_aliases"


def test_neg001_compile_rejects_invalid_regex_pattern() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have(member_kind="method", name_match="regex", pattern="["),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == [
        "compiler_invalid_member_absence_declaration"
    ]
    assert evidence[0].payload["issue"] == "invalid_pattern"


def test_neg001_compile_rejects_signature_mode_for_attribute_member_kind() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have(
            "password",
            member_kind="attribute",
            signature_mode="exact",
        ),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert evidence[0].payload["issue"] == "invalid_signature_mode_for_member_kind"


def test_neg001_compile_emits_v2_method_body_signature_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    def debug_dump(self, verbose: bool) -> str:
        __archtest__: Annotated[
            None,
            does_not_have(signature_mode="exact"),
        ]
        return "trace"
"""
    source_entities = extract_entities(source, role="source")
    source_method = next(
        entity
        for entity in source_entities
        if entity.kind == "method" and entity.name == "debug_dump"
    )

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["NEG001/does_not_have/v2"]
    assert rules[0].selector.source_entity_id == build_canonical_id(
        source_method.role,
        source_method.root_label,
        source_method.module_path,
        "User",
        "class",
        "-",
    )
    assert rules[0].params["name"] == "debug_dump"
    assert rules[0].params["signature_anchor_entity_id"] == source_method.canonical_id
    assert rules[0].params["signature_mode"] == "exact"


def test_neg001_compile_rejects_signature_mode_outside_method_body() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

class User:
    __archtest__: Annotated[
        None,
        does_not_have("debug_dump", member_kind="method", signature_mode="exact"),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert evidence[0].payload["issue"] == "signature_mode_requires_method_body"


def test_neg001_compile_rejects_method_body_on_non_method_entity() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import does_not_have

def build() -> None:
    __archtest__: Annotated[
        None,
        does_not_have(signature_mode="exact"),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
