from __future__ import annotations

from pathlib import Path

from pythonarchtesting.entities import Entity
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.protocols.reference_resolution import (
    module_entity_for,
    normalize_reference,
    resolve_reference,
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


def test_normalize_reference_accepts_parameterized_class_reference() -> None:
    normalized, reason = normalize_reference(
        "Repository[str]",
        module_path="source_module",
    )

    assert reason is None
    assert normalized == "source_module.Repository"


def test_normalize_reference_accepts_single_class_container_reference() -> None:
    normalized, reason = normalize_reference(
        "list[Repository]",
        module_path="source_module",
    )

    assert reason is None
    assert normalized == "source_module.Repository"


def test_resolve_reference_accepts_nested_wrappers_and_aliases() -> None:
    target = """
from typing import Annotated
from target_module import SqlRepository as RepoImpl

class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

def process(repo: object) -> None:
    return None
"""
    target_entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    resolution = resolve_reference(
        'type[Annotated[RepoImpl | None, "marker"]]',
        context_entity=context_entity,
        entities=target_entities,
    )

    assert resolution.reason is None
    assert resolution.normalized == "target_module.SqlRepository"
    assert resolution.entity is not None
    assert resolution.entity.name == "SqlRepository"


def test_resolve_reference_accepts_single_class_container_annotation() -> None:
    target = """
class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

def process(repo: object) -> None:
    return None
"""
    target_entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    resolution = resolve_reference(
        "list[SqlRepository]",
        context_entity=context_entity,
        entities=target_entities,
    )

    assert resolution.reason is None
    assert resolution.normalized == "target_module.SqlRepository"
    assert resolution.entity is not None
    assert resolution.entity.name == "SqlRepository"


def test_resolve_reference_accepts_mapping_value_and_ignores_scalar_key() -> None:
    target = """
from typing import Mapping

class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

def process(repo: object) -> None:
    return None
"""
    target_entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    resolution = resolve_reference(
        "Mapping[str, SqlRepository]",
        context_entity=context_entity,
        entities=target_entities,
    )

    assert resolution.reason is None
    assert resolution.normalized == "target_module.SqlRepository"
    assert resolution.entity is not None
    assert resolution.entity.name == "SqlRepository"


def test_resolve_reference_accepts_nested_wrapper_inside_container_annotation() -> None:
    target = """
from typing import Annotated

class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

def process(repo: object) -> None:
    return None
"""
    target_entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    resolution = resolve_reference(
        'dict[str, Annotated[SqlRepository | None, "marker"]]',
        context_entity=context_entity,
        entities=target_entities,
    )

    assert resolution.reason is None
    assert resolution.normalized == "target_module.SqlRepository"
    assert resolution.entity is not None
    assert resolution.entity.name == "SqlRepository"


def test_resolve_reference_rejects_multi_class_union_as_ambiguous() -> None:
    target = """
class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

class AltRepository:
    def get(self, item_id: str) -> str:
        return item_id

def process(repo: object) -> None:
    return None
"""
    target_entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    resolution = resolve_reference(
        "SqlRepository | AltRepository",
        context_entity=context_entity,
        entities=target_entities,
    )

    assert resolution.entity is None
    assert resolution.reason == "ambiguous_or_missing"


def test_resolve_reference_rejects_multi_class_container_as_ambiguous() -> None:
    target = """
class SqlRepository:
    def get(self, item_id: str) -> str:
        return item_id

class AltRepository:
    def get(self, item_id: str) -> str:
        return item_id

def process(repo: object) -> None:
    return None
"""
    target_entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    resolution = resolve_reference(
        "dict[SqlRepository, AltRepository]",
        context_entity=context_entity,
        entities=target_entities,
    )

    assert resolution.entity is None
    assert resolution.reason == "ambiguous_or_missing"


def test_resolve_reference_rejects_container_without_class_candidate() -> None:
    target = """
def process(repo: object) -> None:
    return None
"""
    target_entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    resolution = resolve_reference(
        "tuple[str, ...]",
        context_entity=context_entity,
        entities=target_entities,
    )

    assert resolution.entity is None
    assert resolution.reason == "unsupported_reference_shape"


def test_module_entity_for_returns_matching_module_entity_without_rescanning_callers() -> (
    None
):
    target = """
class SqlRepository:
    pass

def process(repo: object) -> None:
    return None
"""
    target_entities = _extract_entities(target, role="target")
    context_entity = _extract_entity(
        target, role="target", kind="function", name="process"
    )

    module_entity = module_entity_for(context_entity, target_entities)

    assert module_entity is not None
    assert module_entity.kind == "module"
    assert module_entity.module_path == "target_module"


def test_resolve_reference_is_stable_across_repeated_alias_lookups_in_same_module() -> (
    None
):
    target = """
from target_module import SqlRepository as RepoImpl

class SqlRepository:
    pass

def first(repo: object) -> None:
    return None

def second(repo: object) -> None:
    return None
"""
    target_entities = _extract_entities(target, role="target")
    first_context = _extract_entity(
        target, role="target", kind="function", name="first"
    )
    second_context = _extract_entity(
        target, role="target", kind="function", name="second"
    )

    first_resolution = resolve_reference(
        "RepoImpl",
        context_entity=first_context,
        entities=target_entities,
    )
    second_resolution = resolve_reference(
        "RepoImpl",
        context_entity=second_context,
        entities=target_entities,
    )

    assert first_resolution.reason is None
    assert second_resolution.reason is None
    assert first_resolution.normalized == "target_module.SqlRepository"
    assert second_resolution.normalized == "target_module.SqlRepository"
    assert first_resolution.entity == second_resolution.entity
