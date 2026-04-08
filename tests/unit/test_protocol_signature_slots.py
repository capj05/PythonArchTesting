from __future__ import annotations

import ast
from pathlib import Path

from pythonarchtesting.entities import Entity
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.entities_extraction.annotations import (
    extract_signature_annotation_declarations,
)
from pythonarchtesting.protocols.signature_slots import (
    signature_slots,
    signature_subject_annotation,
)


def _parse_function(source: str) -> ast.FunctionDef:
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.FunctionDef):
            return node
    raise AssertionError("Function definition not found")


def _extract_function_entity(source_text: str, *, name: str) -> Entity:
    entities = extract_entities_from_source(
        source_text=source_text,
        file_path=Path("sample.py"),
        root_path=Path("."),
        target_module_name=None,
        role="target",
        include_nested_functions=False,
        root_label="target",
    )
    for entity in entities:
        if entity.name != name:
            continue
        if entity.kind in {"function", "method"}:
            return entity
    raise AssertionError(f"Function entity '{name}' not found")


def test_signature_slots_skip_instance_receiver_and_preserve_visible_order() -> None:
    function = _parse_function("""
def process(self, first: int, *items: str, flag: bool, **metadata: bytes) -> None:
    return None
""")

    slots = signature_slots(function)

    assert [
        (slot.subject_kind, slot.subject_index, slot.subject_name) for slot in slots
    ] == [
        ("param", -1, "self"),
        ("param", 0, "first"),
        ("param", 1, "items"),
        ("param", 2, "flag"),
        ("param", 3, "metadata"),
        ("return", -1, "return"),
    ]


def test_signature_slots_skip_class_receiver() -> None:
    function = _parse_function("""
def build(cls, repo: object) -> object:
    return repo
""")

    slots = signature_slots(function)

    assert [
        (slot.subject_kind, slot.subject_index, slot.subject_name) for slot in slots
    ] == [
        ("param", -1, "cls"),
        ("param", 0, "repo"),
        ("return", -1, "return"),
    ]


def test_signature_slots_preserve_plain_function_parameter_order() -> None:
    function = _parse_function("""
def combine(left: int, right: str, *, enabled: bool) -> None:
    return None
""")

    slots = signature_slots(function)

    assert [
        (slot.subject_kind, slot.subject_index, slot.subject_name) for slot in slots
    ] == [
        ("param", 0, "left"),
        ("param", 1, "right"),
        ("param", 2, "enabled"),
        ("return", -1, "return"),
    ]


def test_signature_subject_annotation_matches_extracted_signature_subjects() -> None:
    source = """
from typing import Annotated

def process(
    self,
    repo: Annotated[object, ("implements_protocol", {"protocol": "sample.Repository"})],
    service: Annotated[int, ("required_entity_signature", {"signature": "int"})],
) -> Annotated[bytes, ("required_entity_signature", {"signature": "bytes"})]:
    return b""
"""
    function = _parse_function(source)
    entity = _extract_function_entity(source, name="process")

    declarations = extract_signature_annotation_declarations(function, source)

    subject_map = {
        (
            declaration.subject_kind,
            declaration.subject_index,
        ): declaration.base_annotation
        for declaration in declarations
    }

    assert (
        signature_subject_annotation(
            entity,
            subject_kind="param",
            subject_index=0,
        )
        == subject_map[("param", 0)]
    )
    assert (
        signature_subject_annotation(
            entity,
            subject_kind="param",
            subject_index=1,
        )
        == subject_map[("param", 1)]
    )
    assert (
        signature_subject_annotation(
            entity,
            subject_kind="return",
            subject_index=-1,
        )
        == subject_map[("return", -1)]
    )


def test_signature_subject_annotation_skips_receiver_and_preserves_visible_slots() -> (
    None
):
    source = """
def process(
    self,
    first: int,
    *items: str,
    flag: bool,
    **metadata: bytes,
) -> float:
    return 0.0
"""
    entity = _extract_function_entity(source, name="process")

    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=0)
        == "int"
    )
    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=1)
        == "str"
    )
    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=2)
        == "bool"
    )
    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=3)
        == "bytes"
    )
    assert (
        signature_subject_annotation(entity, subject_kind="return", subject_index=-1)
        == "float"
    )


def test_signature_subject_annotation_matches_declarations_for_vararg_and_kwonly_slots() -> (
    None
):
    source = """
from typing import Annotated

def process(
    self,
    first: int,
    *items: Annotated[str, ("implements_protocol", {"protocol": "sample.ItemsProtocol"})],
    flag: Annotated[bool, ("implements_protocol", {"protocol": "sample.FlagProtocol"})],
    **metadata: bytes,
) -> None:
    return None
"""
    function = _parse_function(source)
    entity = _extract_function_entity(source, name="process")

    declarations = extract_signature_annotation_declarations(function, source)

    subject_map = {
        (
            declaration.subject_kind,
            declaration.subject_index,
        ): declaration.base_annotation
        for declaration in declarations
    }

    assert subject_map[("param", 1)] == "str"
    assert subject_map[("param", 2)] == "bool"
    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=1)
        == subject_map[("param", 1)]
    )
    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=2)
        == subject_map[("param", 2)]
    )


def test_signature_subject_annotation_skips_class_receiver() -> None:
    source = """
class Builder:
    def build(cls, repo: object, enabled: bool) -> str:
        return ""
"""
    entity = _extract_function_entity(source, name="build")

    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=0)
        == "object"
    )
    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=1)
        == "bool"
    )
    assert (
        signature_subject_annotation(entity, subject_kind="return", subject_index=-1)
        == "str"
    )


def test_signature_subject_annotation_preserves_plain_function_order() -> None:
    source = """
def combine(left: int, right: str, *, enabled: bool) -> None:
    return None
"""
    entity = _extract_function_entity(source, name="combine")

    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=0)
        == "int"
    )
    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=1)
        == "str"
    )
    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=2)
        == "bool"
    )
    assert (
        signature_subject_annotation(entity, subject_kind="return", subject_index=-1)
        == "None"
    )


def test_signature_subject_annotation_returns_none_for_missing_slot() -> None:
    source = """
def combine(left: int) -> None:
    return None
"""
    entity = _extract_function_entity(source, name="combine")

    assert (
        signature_subject_annotation(entity, subject_kind="param", subject_index=3)
        is None
    )
    assert (
        signature_subject_annotation(entity, subject_kind="attribute", subject_index=0)
        is None
    )
