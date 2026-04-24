from __future__ import annotations

from unittest.mock import Mock

from pythonarchtesting.rules.compilation import compile_rules
from tests.unit.test_rules.protocol_rule_test_helpers import extract_entities


def test_api003_compile_emits_required_attribute_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", annotation="str", storage="instance"),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API003/required_attribute/v1"]
    assert [rule.rule_type for rule in rules] == ["attribute_contract"]
    assert rules[0].params == {
        "name": "email",
        "annotation": "str",
        "storage": "instance",
        "allow_property": False,
        "require_writable": False,
        "declared_only": False,
        "fail_on_unmatched": True,
    }


def test_api003_compile_multiple_required_attributes_get_stable_suffixes() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[None, required_attribute("email", annotation="str")]
    __archtest__: Annotated[
        None,
        required_attribute("VERSION", annotation="str", storage="class"),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == [
        "API003/required_attribute/v1/d0",
        "API003/required_attribute/v1/d1",
    ]


def test_api003_compile_invalid_storage_emits_compiler_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[None, required_attribute("email", storage="weird")]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == [
        "compiler_invalid_attribute_declaration"
    ]
    assert evidence[0].payload["issue"] == "invalid_storage"


def test_api003_compile_non_class_emits_invalid_target_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

def build() -> None:
    __archtest__: Annotated[None, required_attribute("email")]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


def test_api003_compile_threads_new_bool_params() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute(
            "email",
            annotation="str",
            storage="instance",
            allow_property=True,
            require_writable=True,
            declared_only=True,
        ),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert len(rules) == 1
    assert rules[0].params["allow_property"] is True
    assert rules[0].params["require_writable"] is True
    assert rules[0].params["declared_only"] is True


def test_api003_compile_allow_property_with_class_storage_emits_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

class User:
    __archtest__: Annotated[
        None,
        required_attribute("VERSION", storage="class", allow_property=True),
    ]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == [
        "compiler_invalid_attribute_declaration"
    ]
    assert evidence[0].payload["issue"] == "property_incompatible_with_class_storage"
    assert evidence[0].payload["allow_property"] is True
    assert evidence[0].payload["storage"] == "class"


def test_api003_signature_annotation_usage_is_rejected_in_v1() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_attribute

def build(user: Annotated[object, required_attribute("email")]) -> None:
    return None
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]
