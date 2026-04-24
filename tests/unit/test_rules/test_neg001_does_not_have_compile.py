from __future__ import annotations

from unittest.mock import Mock

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
