from __future__ import annotations

import re

from pythonarchtesting.entities import Entity

from .member_name_resolution import (
    matched_target_parent_class,
    target_methods_for_class,
)

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
    ctx: object,
    *,
    allow_inherited: bool,
) -> list[Entity]:
    return [
        method
        for method in target_methods_for_class(
            target_class,
            ctx,  # type: ignore[arg-type]
            include_inherited=allow_inherited,
        )
        if _is_factory_candidate(method)
    ]


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
    "factory_candidates_for_class",
    "factory_kind",
    "filter_factory_candidates",
    "matched_target_parent_class",
]
