from __future__ import annotations

from src.protocols.introspection import (
    is_protocol_entity,
    protocol_attributes,
    protocol_methods,
)
from tests.unit.test_rules.protocol_rule_test_helpers import extract_entities


def test_pro001_is_protocol_entity_accepts_typing_extensions_protocol_inheritance_chain() -> (
    None
):
    source = """
from typing_extensions import Protocol as ExtProtocol

class BaseRepository(ExtProtocol):
    def get(self, item_id: str) -> str:
        ...


class Repository(BaseRepository):
    def save(self, item_id: str) -> None:
        ...
"""
    source_entities = extract_entities(source, role="source")
    base_repository = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "BaseRepository"
    )
    repository = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Repository"
    )

    assert is_protocol_entity(base_repository, source_entities) is True
    assert is_protocol_entity(repository, source_entities) is True


def test_pro001_protocol_collector_includes_inherited_protocol_methods() -> None:
    source = """
from typing import Protocol

class BaseRepository(Protocol):
    def get(self, item_id: str) -> str:
        ...


class Repository(BaseRepository):
    def save(self, item_id: str) -> None:
        ...
"""
    source_entities = extract_entities(source, role="source")
    protocol_entity = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Repository"
    )

    assert [
        method.name for method in protocol_methods(protocol_entity, source_entities)
    ] == ["get", "save"]


def test_pro001_protocol_collector_includes_inherited_protocol_attributes() -> None:
    source = """
from typing import Protocol

class Named(Protocol):
    @property
    def name(self) -> str:
        ...


class Repository(Named, Protocol):
    enabled: bool
"""
    source_entities = extract_entities(source, role="source")
    protocol_entity = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Repository"
    )

    assert [
        (
            attribute.name,
            attribute.kind,
            attribute.annotation,
            attribute.is_writable,
        )
        for attribute in protocol_attributes(protocol_entity, source_entities)
    ] == [
        ("enabled", "attribute", "bool", True),
        ("name", "property", "str", False),
    ]


def test_pro001_protocol_collector_combines_multiple_protocol_bases_deterministically() -> (
    None
):
    source = """
from typing import Protocol

class Reader(Protocol):
    def get(self, item_id: str) -> str:
        ...


class Writer(Protocol):
    def save(self, item_id: str) -> None:
        ...


class Repository(Reader, Writer):
    def ping(self) -> None:
        ...
"""
    source_entities = extract_entities(source, role="source")
    protocol_entity = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Repository"
    )

    assert [
        method.name for method in protocol_methods(protocol_entity, source_entities)
    ] == ["get", "ping", "save"]


def test_pro001_protocol_collector_prefers_child_override_over_inherited_member() -> (
    None
):
    source = """
from typing import Protocol

class BaseRepository(Protocol):
    def get(self, item_id: str) -> str:
        ...


class Repository(BaseRepository):
    def get(self, item_id: int) -> str:
        ...
"""
    source_entities = extract_entities(source, role="source")
    protocol_entity = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Repository"
    )

    methods = protocol_methods(protocol_entity, source_entities)

    assert [method.name for method in methods] == ["get"]
    assert methods[0].extras["annotations"]["args"][1]["annotation"] == "int"


def test_pro001_protocol_collector_treats_property_as_attribute() -> None:
    source = """
from typing import Annotated
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    @property
    def name(self) -> str:
        ...

    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    source_entities = extract_entities(source, role="source")
    protocol_entity = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Repository"
    )

    assert [
        method.name for method in protocol_methods(protocol_entity, source_entities)
    ] == []
    attributes = protocol_attributes(protocol_entity, source_entities)
    assert [
        (
            attribute.name,
            attribute.kind,
            attribute.annotation,
            attribute.is_writable,
        )
        for attribute in attributes
    ] == [("name", "property", "str", False)]


def test_pro001_protocol_collector_deduplicates_attributes_and_ignores_archtest() -> (
    None
):
    source = """
from typing import Annotated
from typing import ClassVar
from typing import Protocol
from src.rules import implements_protocol

class Repository(Protocol):
    name = "fallback"
    name: str
    flag: ClassVar[bool]
    __archtest__: Annotated[None, implements_protocol("source_module.Repository")]
"""
    source_entities = extract_entities(source, role="source")
    protocol_entity = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Repository"
    )

    attributes = protocol_attributes(protocol_entity, source_entities)
    assert [
        (
            attribute.name,
            attribute.annotation,
            attribute.is_writable,
            attribute.is_classvar_deferred,
        )
        for attribute in attributes
    ] == [
        ("flag", "bool", True, True),
        ("name", "str", True, False),
    ]


def test_pro001_protocol_collector_marks_property_with_setter_as_writable() -> None:
    source = """
from typing import Protocol

class Repository(Protocol):
    @property
    def name(self) -> str:
        ...

    @name.setter
    def name(self, value: str) -> None:
        ...
"""
    source_entities = extract_entities(source, role="source")
    protocol_entity = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Repository"
    )

    attributes = protocol_attributes(protocol_entity, source_entities)

    assert [
        (
            attribute.name,
            attribute.kind,
            attribute.annotation,
            attribute.is_writable,
        )
        for attribute in attributes
    ] == [("name", "property", "str", True)]


def test_pro001_is_protocol_entity_walks_multilevel_protocol_bases_consistently() -> None:
    source = """
from typing import Protocol

class Root(Protocol):
    def root(self) -> None:
        ...


class Mid(Root):
    def mid(self) -> None:
        ...


class Leaf(Mid):
    def leaf(self) -> None:
        ...
"""
    source_entities = extract_entities(source, role="source")
    leaf = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Leaf"
    )

    assert is_protocol_entity(leaf, source_entities) is True
    assert [method.name for method in protocol_methods(leaf, source_entities)] == [
        "leaf",
        "mid",
        "root",
    ]


def test_pro001_protocol_collector_merges_multibase_protocol_attributes_deterministically() -> (
    None
):
    source = """
from typing import Protocol

class Named(Protocol):
    name: str


class Enabled(Protocol):
    enabled: bool


class Repository(Named, Enabled):
    version: int
"""
    source_entities = extract_entities(source, role="source")
    protocol_entity = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "Repository"
    )

    assert [
        (attribute.name, attribute.annotation)
        for attribute in protocol_attributes(protocol_entity, source_entities)
    ] == [
        ("enabled", "bool"),
        ("name", "str"),
        ("version", "int"),
    ]
