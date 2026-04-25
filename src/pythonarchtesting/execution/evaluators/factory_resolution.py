from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pythonarchtesting.entities import Entity

from .construction_resolution import (
    constructor_candidates_for_class,
    constructor_origin_for_entity,
)
from .member_name_resolution import (
    matched_target_parent_class,
    target_methods_for_class,
)

if TYPE_CHECKING:
    from pythonarchtesting.core.models import EvalContext

_FACTORY_CONSTRUCTOR_NAMES = frozenset({"__init__", "__new__"})


def factory_kind(entity: Entity) -> str:
    from pythonarchtesting.execution.evaluators.api_signature import _method_kind

    if entity.name in _FACTORY_CONSTRUCTOR_NAMES:
        return "constructor"
    kind = _method_kind(entity)
    if kind == "class":
        return "classmethod"
    if kind == "static":
        return "staticmethod"
    return "unknown"


def _is_factory_candidate(entity: Entity) -> bool:
    return factory_kind(entity) != "unknown"


def factory_candidates_for_class(
    target_class: Entity,
    ctx: EvalContext,
    *,
    allow_inherited: bool,
) -> list[Entity]:
    target_entities = ctx.target_index.all_sorted
    constructor_entities = [
        candidate.entity
        for candidate in constructor_candidates_for_class(
            target_class,
            target_entities,
            allow_inherited=allow_inherited,
        )
    ]
    method_entities = [
        method
        for method in target_methods_for_class(
            target_class,
            ctx,
            include_inherited=allow_inherited,
        )
        if _is_factory_candidate(method)
        and method.name not in _FACTORY_CONSTRUCTOR_NAMES
    ]
    return [*constructor_entities, *method_entities]


def factory_candidate_origin(
    entity: Entity,
    target_class: Entity,
    ctx: EvalContext,
) -> str:
    if entity.name in _FACTORY_CONSTRUCTOR_NAMES:
        target_entities = ctx.target_index.all_sorted
        return constructor_origin_for_entity(
            entity,
            target_class,
            target_entities,
        )
    from .member_name_resolution import member_origin

    return member_origin(entity, target_class, ctx)


def filter_factory_candidates(
    candidates: list[Entity],
    *,
    satisfy_with: list[str],
    name_match: str,
    source_name: str,
    aliases: list[str] | None,
    pattern: str | None,
) -> list[Entity]:
    result: list[Entity] = []
    for candidate in candidates:
        candidate_kind = factory_kind(candidate)
        if candidate_kind not in satisfy_with:
            continue
        if candidate_kind == "constructor":
            result.append(candidate)
            continue
        if name_match == "any":
            result.append(candidate)
        elif name_match == "exact" and candidate.name == source_name:
            result.append(candidate)
        elif name_match == "alias" and aliases and candidate.name in aliases:
            result.append(candidate)
        elif (
            name_match == "regex" and pattern and re.fullmatch(pattern, candidate.name)
        ):
            result.append(candidate)
    return result


__all__ = [
    "factory_candidate_origin",
    "factory_candidates_for_class",
    "factory_kind",
    "filter_factory_candidates",
    "matched_target_parent_class",
]
