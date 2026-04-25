from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules


def extract_modules(
    modules: list[tuple[str, str]],
    *,
    role: str,
) -> list[Entity]:
    return [
        entity
        for path, text in modules
        for entity in extract_entities_from_source(
            textwrap.dedent(text).strip() + "\n",
            Path(path),
            Path("."),
            None,
            role=role,  # type: ignore[arg-type]
            include_nested_functions=False,
            root_label=role,
        )
    ]


def entity(
    entities: list[Entity],
    *,
    kind: str,
    module_path: str,
    name: str,
) -> Entity:
    for candidate in entities:
        if (
            candidate.kind == kind
            and candidate.module_path == module_path
            and candidate.name == name
        ):
            return candidate
    raise AssertionError(
        f"Entity not found: kind={kind!r}, module_path={module_path!r}, name={name!r}"
    )


def matched(source: Entity, target: Entity) -> MatchResult:
    return MatchResult(
        source_id=source.canonical_id,
        status=MatchStatus.MATCHED,
        target_id=target.canonical_id,
        confidence=1.0,
        reasons=[],
        candidates=[],
    )


def match_with_status(source: Entity, status: MatchStatus) -> MatchResult:
    return MatchResult(
        source_id=source.canonical_id,
        status=status,
        target_id=None,
        confidence=0.0,
        reasons=[],
        candidates=[],
    )


def evaluate_nom001_rule(
    *,
    rule_id: str,
    source_modules: list[tuple[str, str]],
    target_modules: list[tuple[str, str]],
    source_module_path: str,
    matches: list[MatchResult],
) -> tuple[list[object], list[object]]:
    source_entities = extract_modules(source_modules, role="source")
    target_entities = extract_modules(target_modules, role="target")

    source_entity = entity(
        source_entities,
        kind="class",
        module_path=source_module_path,
        name="CsvRepository",
    )
    rules, _, _ = compile_rules(source_entities, Mock())
    rule = next(
        candidate
        for candidate in rules
        if candidate.rule_id == rule_id
        and candidate.selector.source_entity_id == source_entity.canonical_id
    )

    return evaluate_rules_for_target(
        rules=[rule],
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches={match.source_id: match for match in matches},
        config=Mock(),
    )
