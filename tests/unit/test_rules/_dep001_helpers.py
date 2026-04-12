from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, EntityIndex, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult
from pythonarchtesting.rules.compilation import compile_rules

_RULE_MARKER_NAME = "_architecture_rules_marker"


def extract_all_entities(
    source_text: str,
    *,
    role: str,
    file_path: str,
) -> list[Entity]:
    return extract_entities_from_source(
        source_text=source_text,
        file_path=Path(file_path),
        root_path=Path("."),
        target_module_name=None,
        role=role,  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label=role,
    )


def get_entity(
    entities: list[Entity],
    *,
    kind: str,
    name: str,
) -> Entity:
    for entity in entities:
        if entity.kind == kind and entity.name == name:
            return entity
    raise AssertionError(f"Entity '{name}' ({kind}) not found")


def build_target_index_from_files(files: dict[str, str]) -> EntityIndex:
    entities: list[Entity] = []
    for file_path, source_text in files.items():
        entities.extend(
            extract_all_entities(
                source_text,
                role="target",
                file_path=file_path,
            )
        )
    return build_entity_index(entities)


def build_source_index_from_rule_source(
    source_text: str,
    *,
    file_path: str = "assignment/rules.py",
) -> tuple[Entity, EntityIndex]:
    entities = extract_all_entities(
        source_text,
        role="source",
        file_path=file_path,
    )
    source_entity = get_entity(
        entities,
        kind="function",
        name=_RULE_MARKER_NAME,
    )
    return source_entity, build_entity_index(entities)


def evaluate_dep001_rule(
    *,
    source_entity: Entity,
    source_index: EntityIndex,
    target_index: EntityIndex,
    match: MatchResult,
):
    rules, _, _ = compile_rules([source_entity], Mock())
    matches = {source_entity.canonical_id: match}
    return evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )
