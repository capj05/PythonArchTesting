from __future__ import annotations

from unittest.mock import Mock

from src.rules.compilation import compile_rules
from tests.unit.test_rules.protocol_rule_test_helpers import extract_entities


def test_pro001_compile_emits_protocol_rule() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]

    def get(self, item_id: str) -> str:
        return item_id
"""
    source_entities = extract_entities(source, role="source")
    source_entity = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "SqlRepository"
    )

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    protocol_rules = [
        rule
        for rule in rules
        if rule.selector.source_entity_id == source_entity.canonical_id
    ]
    assert [rule.rule_id for rule in protocol_rules] == [
        "PRO001/implements_protocol/v1"
    ]
    assert protocol_rules[0].rule_type == "protocol_conformance"
    assert protocol_rules[0].params["protocol"] == "source_module.Repository"
    assert ":Repository:class:" in protocol_rules[0].params["protocol_entity_id"]
    assert protocol_rules[0].params["signature_mode"] == "compatible"
    assert protocol_rules[0].params["enforce_method_kind"] is True
    assert protocol_rules[0].params["return_annotation"] == "warning"
    assert protocol_rules[0].params["fail_on_unmatched"] is True
    assert "protocol_method_ids" not in protocol_rules[0].params
    assert "protocol_attribute_names" not in protocol_rules[0].params


def test_pro001_compile_non_class_emits_invalid_target_evidence() -> None:
    source = """
from typing import Annotated
from src.rules import implements_protocol

def build() -> None:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    source_entity = next(
        entity
        for entity in extract_entities(source, role="source")
        if entity.kind == "function" and entity.name == "build"
    )

    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


def test_pro001_compile_missing_protocol_reference_emits_compiler_evidence() -> None:
    source = """
from typing import Annotated

class SqlRepository:
    __archtest__: Annotated[None, ("implements_protocol", {"protocol": "source_module.Missing"})]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_protocol_reference"]


def test_pro001_compile_non_protocol_reference_emits_compiler_evidence() -> None:
    source = """
from typing import Annotated
from src.rules import implements_protocol

class Repository:
    def get(self, item_id: str) -> str:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_protocol_reference"]
    assert evidence[0].payload["reason"] == "not_typing_protocol"


def test_pro001_compile_accepts_wrapped_protocol_reference() -> None:
    source = """
from typing import Annotated
from typing import Optional
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol(Optional[Repository[str]])]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["PRO001/implements_protocol/v1"]
    assert rules[0].params["protocol"] == "source_module.Repository"


def test_pro001_compile_accepts_single_class_container_protocol_reference() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol(dict[str, Repository])]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["PRO001/implements_protocol/v1"]
    assert rules[0].params["protocol"] == "source_module.Repository"


def test_pro001_compile_accepts_protocol_alias_and_indirect_protocol_base() -> None:
    source = """
from typing import Annotated
from typing import Protocol as TypingProtocol
from src.rules import implements_protocol

class BaseRepository(TypingProtocol):
    def get(self, item_id: str) -> str:
        ...


class Repository(BaseRepository):
    def save(self, item_id: str) -> None:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol(Repository)]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["PRO001/implements_protocol/v1"]


def test_pro001_compile_accepts_typing_extensions_protocol_direct_import() -> None:
    source = """
from typing import Annotated
from typing_extensions import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol(Repository)]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["PRO001/implements_protocol/v1"]
    assert rules[0].params["protocol"] == "source_module.Repository"


def test_pro001_compile_accepts_typing_extensions_protocol_alias_and_indirect_base() -> None:
    source = """
from typing import Annotated
from typing_extensions import Protocol as ExtProtocol
from src.rules import implements_protocol

class BaseRepository(ExtProtocol):
    def get(self, item_id: str) -> str:
        ...


class Repository(BaseRepository):
    def save(self, item_id: str) -> None:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol(Repository)]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["PRO001/implements_protocol/v1"]


def test_pro001_compile_does_not_require_runtime_checkable() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    def get(self, item_id: str) -> str:
        ...


class SqlRepository:
    __archtest__: Annotated[None, implements_protocol(Repository)]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["PRO001/implements_protocol/v1"]
