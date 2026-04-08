from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules


def extract_entities(source_text: str, *, role: str) -> list[Entity]:
    return extract_entities_from_source(
        source_text=source_text,
        file_path=Path(f"{role}_module.py"),
        root_path=Path("."),
        target_module_name=None,
        role=role,  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label=role,
    )


def extract_entity(
    source_text: str,
    *,
    role: str,
    kind: str,
    name: str,
) -> Entity:
    for entity in extract_entities(source_text, role=role):
        if entity.kind == kind and entity.name == name:
            return entity
    raise AssertionError(f"Entity '{name}' ({kind}) not found for role={role}")


def match_for(source_entity: Entity, target_entity: Entity) -> dict[str, MatchResult]:
    return {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }


def select_rule(
    rules: list[object],
    *,
    rule_id: str | None = None,
    subject_kind: str | None = None,
) -> object:
    for rule in rules:
        if rule_id is not None and rule.rule_id != rule_id:
            continue
        if subject_kind is not None and rule.params.get("subject_kind") != subject_kind:
            continue
        return rule
    raise AssertionError(
        f"Rule not found for rule_id={rule_id!r}, subject_kind={subject_kind!r}"
    )


def evaluate_single_rule(
    *,
    source_text: str,
    target_text: str,
    source_kind: str,
    source_name: str,
    target_kind: str,
    target_name: str,
    rule_id: str | None = None,
    subject_kind: str | None = None,
) -> tuple[list[object], list[object], object]:
    source_entities = extract_entities(source_text, role="source")
    target_entities = extract_entities(target_text, role="target")
    source_entity = extract_entity(
        source_text, role="source", kind=source_kind, name=source_name
    )
    target_entity = extract_entity(
        target_text, role="target", kind=target_kind, name=target_name
    )
    rules, _, _ = compile_rules(source_entities, Mock())
    selected_rule = select_rule(
        rules,
        rule_id=rule_id,
        subject_kind=subject_kind,
    )
    results, errors = evaluate_rules_for_target(
        rules=[selected_rule],
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=match_for(source_entity, target_entity),
        config=Mock(),
    )
    return results, errors, selected_rule
