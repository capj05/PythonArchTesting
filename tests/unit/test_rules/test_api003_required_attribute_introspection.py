from __future__ import annotations

from pythonarchtesting.protocols.attribute_introspection import (
    collect_attributes,
    direct_declared_class_attributes,
    direct_declared_instance_attributes,
    direct_declared_property_attributes,
)
from tests.unit.test_rules.protocol_rule_test_helpers import extract_entities


def test_api003_collects_direct_class_attributes_and_normalizes_classvar() -> None:
    source = """
from typing import ClassVar

class User:
    email: str
    VERSION = "1"
    FLAG: ClassVar[int]
"""
    source_entities = extract_entities(source, role="source")
    user = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "User"
    )

    attributes = direct_declared_class_attributes(user)

    assert [
        (attribute.name, attribute.annotation, attribute.storage, attribute.origin)
        for attribute in attributes
    ] == [
        ("FLAG", "int", "class", "class_annassign"),
        ("VERSION", None, "class", "class_assign"),
        ("email", "str", "class", "class_annassign"),
    ]


def test_api003_collects_direct_instance_attributes() -> None:
    source = """
class User:
    def __init__(self) -> None:
        self.email = "user@example.com"
        self.age: int = 1
"""
    source_entities = extract_entities(source, role="source")
    user = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "User"
    )

    attributes = direct_declared_instance_attributes(user, source_entities)

    assert [
        (attribute.name, attribute.annotation, attribute.storage, attribute.origin)
        for attribute in attributes
    ] == [
        ("age", "int", "instance", "self_annassign"),
        ("email", None, "instance", "self_assign"),
    ]


def test_api003_collects_inherited_attributes() -> None:
    source = """
class Base:
    token: str


class User(Base):
    pass
"""
    source_entities = extract_entities(source, role="source")
    user = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "User"
    )

    attributes = collect_attributes(
        user,
        source_entities,
        include_inherited=True,
        include_instance=False,
        include_class=True,
        include_properties=False,
    )

    assert "token" in attributes
    assert attributes["token"][0].name == "token"
    assert attributes["token"][0].inherited is True


def test_api003_collects_properties_without_reusing_protocol_attribute_semantics() -> (
    None
):
    source = """
class User:
    @property
    def email(self) -> str:
        return "user@example.com"
"""
    source_entities = extract_entities(source, role="source")
    user = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "User"
    )

    properties = direct_declared_property_attributes(user)
    collected = collect_attributes(
        user,
        source_entities,
        include_inherited=False,
        include_instance=False,
        include_class=False,
        include_properties=True,
    )

    assert [
        (attribute.name, attribute.annotation, attribute.storage, attribute.origin)
        for attribute in properties
    ] == [("email", "str", "property", "property")]
    assert [
        (attribute.name, attribute.storage) for attribute in collected["email"]
    ] == [("email", "property")]


def test_api003_property_without_setter_has_is_writable_false() -> None:
    source = """
class User:
    @property
    def email(self) -> str:
        return "user@example.com"
"""
    source_entities = extract_entities(source, role="source")
    user = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "User"
    )

    properties = direct_declared_property_attributes(user)

    assert len(properties) == 1
    assert properties[0].name == "email"
    assert properties[0].is_writable is False


def test_api003_property_with_setter_has_is_writable_true() -> None:
    source = """
class User:
    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        self._email = value
"""
    source_entities = extract_entities(source, role="source")
    user = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "User"
    )

    properties = direct_declared_property_attributes(user)

    assert len(properties) == 1
    assert properties[0].name == "email"
    assert properties[0].is_writable is True


def test_api003_regular_class_attribute_has_is_writable_true() -> None:
    source = """
class User:
    email: str
    VERSION = "1"
"""
    source_entities = extract_entities(source, role="source")
    user = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "User"
    )

    attributes = direct_declared_class_attributes(user)

    assert all(attribute.is_writable is True for attribute in attributes)


def test_api003_regular_instance_attribute_has_is_writable_true() -> None:
    source = """
class User:
    def __init__(self) -> None:
        self.email = "user@example.com"
        self.age: int = 1
"""
    source_entities = extract_entities(source, role="source")
    user = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "User"
    )

    attributes = direct_declared_instance_attributes(user, source_entities)

    assert all(attribute.is_writable is True for attribute in attributes)


def test_api003_prefers_local_annotated_attribute_over_inherited_unannotated_one() -> (
    None
):
    source = """
class Base:
    value = 1


class User(Base):
    value: int
"""
    source_entities = extract_entities(source, role="source")
    user = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "User"
    )

    attributes = collect_attributes(
        user,
        source_entities,
        include_inherited=True,
        include_instance=False,
        include_class=True,
        include_properties=False,
    )

    assert [
        (attribute.annotation, attribute.inherited) for attribute in attributes["value"]
    ] == [
        ("int", False),
        (None, True),
    ]
