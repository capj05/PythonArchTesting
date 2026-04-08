from __future__ import annotations

from pathlib import Path

from pythonarchtesting.core.models import EvalContext
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.execution.evaluators.annotation_compatibility import (
    compare_annotation_text,
    normalize_annotation_text,
)


def _extract_entities(source_text: str, *, role: str) -> list[Entity]:
    return extract_entities_from_source(
        source_text=source_text,
        file_path=Path(f"{role}_module.py"),
        root_path=Path("."),
        target_module_name=None,
        role=role,  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label=role,
    )


def _extract_entity(
    source_text: str,
    *,
    role: str,
    kind: str,
    name: str,
) -> Entity:
    for entity in _extract_entities(source_text, role=role):
        if entity.kind == kind and entity.name == name:
            return entity
    raise AssertionError(f"Entity '{name}' ({kind}) not found for role={role}")


def _ctx(source_entities: list[Entity], target_entities: list[Entity]) -> EvalContext:
    return EvalContext(
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches={},
        config=None,
        source_by_id={entity.canonical_id: entity for entity in source_entities},
        target_by_id={entity.canonical_id: entity for entity in target_entities},
    )


def test_normalize_annotation_text_unwraps_annotated_aliases() -> None:
    target = """
from typing import Annotated
from target_module import SqlRepository as RepoImpl

class SqlRepository:
    pass

def process(repo: object) -> None:
    return None
"""
    entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    normalized = normalize_annotation_text(
        'Annotated[RepoImpl, "marker"]',
        context_entity=context_entity,
        entities=entities,
    )

    assert normalized == "target_module.SqlRepository"


def test_normalize_annotation_text_treats_optional_like_union_none() -> None:
    target = """
from typing import Optional

class Repository:
    pass

def process(repo: object) -> None:
    return None
"""
    entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    optional_normalized = normalize_annotation_text(
        "Optional[Repository]",
        context_entity=context_entity,
        entities=entities,
    )
    union_normalized = normalize_annotation_text(
        "Repository | None",
        context_entity=context_entity,
        entities=entities,
    )

    assert optional_normalized == union_normalized == "None | target_module.Repository"


def test_normalize_annotation_text_preserves_type_wrapper_for_nested_wrappers() -> None:
    target = """
from typing import Annotated

class Repository:
    pass

def process(repo: object) -> None:
    return None
"""
    entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    normalized = normalize_annotation_text(
        'type[Annotated[Repository | None, "marker"]]',
        context_entity=context_entity,
        entities=entities,
    )

    assert normalized == "type[None | target_module.Repository]"


def test_normalize_annotation_text_flattens_typing_union_and_pipe_union_the_same() -> (
    None
):
    target = """
from typing import Union

class Repository:
    pass

class Service:
    pass

def process(repo: object) -> None:
    return None
"""
    entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    typing_union = normalize_annotation_text(
        "Union[Repository, Service, None]",
        context_entity=context_entity,
        entities=entities,
    )
    pipe_union = normalize_annotation_text(
        "Repository | Service | None",
        context_entity=context_entity,
        entities=entities,
    )

    assert typing_union == pipe_union
    assert pipe_union == ("None | target_module.Repository | target_module.Service")


def test_compare_annotation_text_uses_aliases_consistently_after_refactor() -> None:
    source = """
class Repository:
    pass

def expected() -> None:
    return None
"""
    target = """
from target_module import Repository as RepoImpl

class Repository:
    pass

def found() -> None:
    return None
"""
    source_entities = _extract_entities(source, role="source")
    target_entities = _extract_entities(target, role="target")
    expected_entity = _extract_entity(
        source, role="source", kind="function", name="expected"
    )
    found_entity = _extract_entity(target, role="target", kind="function", name="found")

    comparison = compare_annotation_text(
        expected="Repository",
        found="RepoImpl",
        expected_entity=expected_entity,
        found_entity=found_entity,
        ctx=_ctx(source_entities, target_entities),
        variance="invariant",
    )

    assert comparison.compatible is True
    assert comparison.expected == "source_module.Repository"
    assert comparison.found == "target_module.Repository"


def test_normalize_annotation_text_preserves_attribute_suffix_when_alias_root_is_rewritten() -> (
    None
):
    target = """
from vendor import pkg

def process(repo: object) -> None:
    return None
"""
    entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    normalized = normalize_annotation_text(
        "pkg.Repository.Inner",
        context_entity=context_entity,
        entities=entities,
    )

    assert normalized == "vendor.pkg.Repository.Inner"


def test_compare_annotation_text_accepts_covariant_subtype_through_multilevel_inheritance() -> (
    None
):
    source = """
class BaseRepository:
    pass

def expected() -> None:
    return None
"""
    target = """
class BaseRepository:
    pass

class Repository(BaseRepository):
    pass

class SqlRepository(Repository):
    pass

def found() -> None:
    return None
"""
    source_entities = _extract_entities(source, role="source")
    target_entities = _extract_entities(target, role="target")
    expected_entity = _extract_entity(
        source, role="source", kind="function", name="expected"
    )
    found_entity = _extract_entity(target, role="target", kind="function", name="found")

    comparison = compare_annotation_text(
        expected="BaseRepository",
        found="SqlRepository",
        expected_entity=expected_entity,
        found_entity=found_entity,
        ctx=_ctx(source_entities, target_entities),
        variance="covariant",
    )

    assert comparison.compatible is True
    assert comparison.expected == "source_module.BaseRepository"
    assert comparison.found == "target_module.SqlRepository"


def test_compare_annotation_text_accepts_contravariant_supertype_through_cached_name_lookup() -> (
    None
):
    source = """
class Repository:
    pass

def expected() -> None:
    return None
"""
    target = """
class BaseRepository:
    pass

class Repository(BaseRepository):
    pass

class SqlRepository(Repository):
    pass

def found() -> None:
    return None
"""
    source_entities = _extract_entities(source, role="source")
    target_entities = _extract_entities(target, role="target")
    expected_entity = _extract_entity(
        source, role="source", kind="function", name="expected"
    )
    found_entity = _extract_entity(target, role="target", kind="function", name="found")

    comparison = compare_annotation_text(
        expected="Repository",
        found="BaseRepository",
        expected_entity=expected_entity,
        found_entity=found_entity,
        ctx=_ctx(source_entities, target_entities),
        variance="contravariant",
    )

    assert comparison.compatible is True
    assert comparison.expected == "source_module.Repository"
    assert comparison.found == "target_module.BaseRepository"
