from __future__ import annotations

from unittest.mock import Mock

from pythonarchtesting.rules.compilation import compile_rules
from tests.unit.test_rules.protocol_rule_test_helpers import extract_entities


def test_pro002_compile_emits_rules_for_param_and_return_slots() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from pythonarchtesting.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...

def build(
    repo: Annotated[object, implements_protocol(Repository)],
) -> Annotated[object, implements_protocol(Repository)]:
    return repo
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "PRO002/implements_protocol_signature/v1/d0",
        "PRO002/implements_protocol_signature/v1/d1",
    ]
    assert [
        (rule.params["subject_kind"], rule.params["subject_index"]) for rule in rules
    ] == [
        ("param", 0),
        ("return", -1),
    ]
    assert all(rule.params["protocol"].endswith("Repository") for rule in rules)
    assert all(
        ":Repository:class:" in rule.params["protocol_entity_id"] for rule in rules
    )
    assert all(rule.params["signature_mode"] == "compatible" for rule in rules)
    assert all(rule.params["enforce_method_kind"] is True for rule in rules)
    assert all(rule.params["return_annotation"] == "warning" for rule in rules)
    assert all(rule.params["fail_on_unmatched"] is True for rule in rules)
    assert all("protocol_method_ids" not in rule.params for rule in rules)
    assert all("protocol_attribute_names" not in rule.params for rule in rules)


def test_pro002_compile_non_protocol_reference_emits_compiler_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import implements_protocol

class Repository:
    def get(self, item_id: str) -> str:
        ...

def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_protocol_reference"]
    assert evidence[0].payload["reason"] == "not_typing_protocol"


def test_pro002_compile_accepts_protocol_alias_and_indirect_protocol_base() -> None:
    source = """
from typing import Annotated
from typing import Protocol as TypingProtocol
from pythonarchtesting.rules import implements_protocol

class BaseRepository(TypingProtocol):
    def get(self, item_id: str) -> str:
        ...


class Repository(BaseRepository):
    def save(self, item_id: str) -> None:
        ...


def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == [
        "PRO002/implements_protocol_signature/v1"
    ]


def test_pro002_compile_accepts_typing_extensions_protocol_direct_import() -> None:
    source = """
from typing import Annotated
from typing_extensions import Protocol
from pythonarchtesting.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...

def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == [
        "PRO002/implements_protocol_signature/v1"
    ]
    assert rules[0].params["protocol"] == "source_module.Repository"


def test_pro002_compile_accepts_typing_extensions_protocol_alias_and_indirect_base() -> (
    None
):
    source = """
from typing import Annotated
from typing_extensions import Protocol as ExtProtocol
from pythonarchtesting.rules import implements_protocol

class BaseRepository(ExtProtocol):
    def get(self, item_id: str) -> str:
        ...


class Repository(BaseRepository):
    def save(self, item_id: str) -> None:
        ...


def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == [
        "PRO002/implements_protocol_signature/v1"
    ]


def test_pro002_compile_does_not_require_runtime_checkable() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from pythonarchtesting.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...

def process(repo: Annotated[object, implements_protocol(Repository)]) -> None:
    return None
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == [
        "PRO002/implements_protocol_signature/v1"
    ]
