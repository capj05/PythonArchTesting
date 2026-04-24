from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchStatus
from pythonarchtesting.protocols.introspection import (
    class_methods,
    declared_class_methods,
)

if TYPE_CHECKING:
    from pythonarchtesting.core.models import EvalContext


def _enclosing_class_qualname(entity: Entity) -> str | None:
    if entity.kind != "method" or "." not in entity.qualname:
        return None
    return entity.qualname.rsplit(".", 1)[0]


def _find_class_entity(
    entities: list[Entity],
    *,
    module_path: str,
    qualname: str,
) -> Entity | None:
    for entity in entities:
        if (
            entity.kind == "class"
            and entity.module_path == module_path
            and entity.qualname == qualname
        ):
            return entity
    return None


def source_parent_class(source_method: Entity, ctx: EvalContext) -> Entity | None:
    class_qualname = _enclosing_class_qualname(source_method)
    if class_qualname is None:
        return None
    return _find_class_entity(
        ctx.source_index.all_sorted,
        module_path=source_method.module_path,
        qualname=class_qualname,
    )


def matched_target_parent_class(
    source_method: Entity, ctx: EvalContext
) -> Entity | None:
    source_class = source_parent_class(source_method, ctx)
    if source_class is None:
        return None

    class_match = ctx.matches.get(source_class.canonical_id)
    if class_match is None or class_match.status != MatchStatus.MATCHED:
        return None
    if not class_match.target_id:
        return None

    target_class = ctx.target_by_id.get(class_match.target_id)
    if not isinstance(target_class, Entity) or target_class.kind != "class":
        return None
    return target_class


def target_parent_class(target_method: Entity, ctx: EvalContext) -> Entity | None:
    class_qualname = _enclosing_class_qualname(target_method)
    if class_qualname is None:
        return None
    return _find_class_entity(
        ctx.target_index.all_sorted,
        module_path=target_method.module_path,
        qualname=class_qualname,
    )


def target_methods_for_class(
    target_class: Entity,
    ctx: EvalContext,
    *,
    include_inherited: bool = True,
) -> list[Entity]:
    if include_inherited:
        return class_methods(target_class, ctx.target_index.all_sorted)
    return declared_class_methods(target_class, ctx.target_index.all_sorted)


def filter_methods_by_name_match(
    methods: list[Entity],
    *,
    source_name: str,
    name_match: str,
    aliases: list[str] | None,
    pattern: str | None,
) -> list[Entity]:
    if name_match == "any":
        return list(methods)
    if name_match == "regex":
        if pattern is None:
            return []
        return [method for method in methods if re.fullmatch(pattern, method.name)]

    accepted_names = {source_name}
    if name_match == "alias":
        accepted_names.update(alias for alias in aliases or [])
    return [method for method in methods if method.name in accepted_names]


def member_origin(
    method: Entity,
    target_class: Entity,
    ctx: EvalContext,
) -> str:
    declared_ids = {
        candidate.canonical_id
        for candidate in target_methods_for_class(
            target_class,
            ctx,
            include_inherited=False,
        )
    }
    return "declared" if method.canonical_id in declared_ids else "inherited"


__all__ = [
    "filter_methods_by_name_match",
    "matched_target_parent_class",
    "member_origin",
    "source_parent_class",
    "target_methods_for_class",
    "target_parent_class",
]
