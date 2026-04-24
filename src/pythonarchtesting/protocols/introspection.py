from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Callable, Sequence, TypeVar

from pythonarchtesting.entities import Entity
from pythonarchtesting.protocols.entity_lookup import ProtocolEntityLookup
from pythonarchtesting.protocols.type_expr import (
    classvar_inner_annotation,
    dotted_name,
    safe_unparse,
)

_PROTOCOL_ROOT_REFERENCES = {
    "typing.Protocol",
    "typing_extensions.Protocol",
}


@dataclass(frozen=True)
class ProtocolAttribute:
    name: str
    annotation: str | None
    kind: str
    is_writable: bool
    is_classvar_deferred: bool
    lineno: int


_MemberT = TypeVar("_MemberT", Entity, ProtocolAttribute)


def protocol_methods(
    protocol_entity: Entity, entities: Sequence[Entity]
) -> list[Entity]:
    lookup = ProtocolEntityLookup.from_entities(entities)
    return _collect_class_methods(
        protocol_entity,
        entities,
        include_base=lambda base_entity: is_protocol_entity(
            base_entity, entities, lookup=lookup
        ),
        lookup=lookup,
    )


def protocol_attributes(
    protocol_entity: Entity, entities: Sequence[Entity]
) -> list[ProtocolAttribute]:
    lookup = ProtocolEntityLookup.from_entities(entities)
    return _collect_class_attributes(
        protocol_entity,
        entities,
        include_base=lambda base_entity: is_protocol_entity(
            base_entity, entities, lookup=lookup
        ),
        lookup=lookup,
    )


def class_attributes(
    entity: Entity, entities: Sequence[Entity]
) -> list[ProtocolAttribute]:
    lookup = ProtocolEntityLookup.from_entities(entities)
    return _collect_class_attributes(
        entity,
        entities,
        include_base=lambda _: True,
        lookup=lookup,
    )


def declared_class_attributes(
    entity: Entity, entities: Sequence[Entity]
) -> list[ProtocolAttribute]:
    lookup = ProtocolEntityLookup.from_entities(entities)
    return _collect_class_attributes(
        entity,
        entities,
        include_base=lambda _: False,
        lookup=lookup,
    )


def class_methods(entity: Entity, entities: Sequence[Entity]) -> list[Entity]:
    lookup = ProtocolEntityLookup.from_entities(entities)
    return _collect_class_methods(
        entity,
        entities,
        include_base=lambda _: True,
        lookup=lookup,
    )


def declared_class_methods(entity: Entity, entities: Sequence[Entity]) -> list[Entity]:
    lookup = ProtocolEntityLookup.from_entities(entities)
    return _collect_class_methods(
        entity,
        entities,
        include_base=lambda _: False,
        lookup=lookup,
    )


def is_protocol_entity(
    protocol_entity: Entity,
    entities: Sequence[Entity],
    *,
    lookup: ProtocolEntityLookup | None = None,
) -> bool:
    active_lookup = lookup or ProtocolEntityLookup.from_entities(entities)
    return _is_protocol_entity(
        protocol_entity,
        entities,
        visited=set(),
        lookup=active_lookup,
    )


def _collect_class_methods(
    entity: Entity,
    entities: Sequence[Entity],
    *,
    include_base: Callable[[Entity], bool],
    lookup: ProtocolEntityLookup,
) -> list[Entity]:
    collected = _collect_members(
        entity,
        entities,
        include_base=include_base,
        local_members_getter=_direct_class_methods,
        sort_key=lambda member: (member.name, member.qualname, member.lineno),
        lookup=lookup,
    )
    return list(collected.values())


def _collect_class_attributes(
    entity: Entity,
    entities: Sequence[Entity],
    *,
    include_base: Callable[[Entity], bool],
    lookup: ProtocolEntityLookup,
) -> list[ProtocolAttribute]:
    collected = _collect_members(
        entity,
        entities,
        include_base=include_base,
        local_members_getter=_direct_class_attributes,
        sort_key=lambda member: (member.name, member.lineno),
        lookup=lookup,
    )
    return list(collected.values())


def _collect_members(
    entity: Entity,
    entities: Sequence[Entity],
    *,
    include_base: Callable[[Entity], bool],
    local_members_getter: Callable[[Entity, Sequence[Entity]], list[_MemberT]],
    sort_key: Callable[[_MemberT], tuple[int | str, ...]],
    lookup: ProtocolEntityLookup,
    visited: set[str] | None = None,
) -> dict[str, _MemberT]:
    if visited is None:
        visited = set()
    if entity.kind != "class" or entity.canonical_id in visited:
        return {}

    visited.add(entity.canonical_id)
    members: dict[str, _MemberT] = {}
    for base_entity in _resolved_base_entities(entity, entities, lookup=lookup):
        if not include_base(base_entity):
            continue
        for name, member in _collect_members(
            base_entity,
            entities,
            include_base=include_base,
            local_members_getter=local_members_getter,
            sort_key=sort_key,
            lookup=lookup,
            visited=visited,
        ).items():
            members.setdefault(name, member)

    for member in sorted(local_members_getter(entity, entities), key=sort_key):
        members[member.name] = member

    return dict(sorted(members.items(), key=lambda item: sort_key(item[1])))


def _resolved_base_entities(
    entity: Entity,
    entities: Sequence[Entity],
    *,
    lookup: ProtocolEntityLookup,
) -> list[Entity]:
    _ = entities
    return list(lookup.resolved_bases(entity))


def _direct_class_methods(entity: Entity, entities: Sequence[Entity]) -> list[Entity]:
    prefix = f"{entity.qualname}."
    methods = [
        candidate
        for candidate in entities
        if candidate.module_path == entity.module_path
        and candidate.kind == "method"
        and candidate.qualname.startswith(prefix)
        and not bool(candidate.surface_meta.get("property"))
    ]
    methods.sort(
        key=lambda candidate: (candidate.name, candidate.qualname, candidate.lineno)
    )
    return methods


def _direct_class_attributes(
    entity: Entity, entities: Sequence[Entity]
) -> list[ProtocolAttribute]:
    _ = entities
    node = entity.extras.get("ast_node")
    if not isinstance(node, ast.ClassDef):
        return []

    property_setters = _property_setter_names(node.body)
    members: dict[str, ProtocolAttribute] = {}
    for stmt in node.body:
        member = _class_member_from_stmt(stmt, property_setters=property_setters)
        if member is None or member.name == "__archtest__":
            continue
        if member.name.startswith("__") and member.name.endswith("__"):
            continue
        current = members.get(member.name)
        if current is None or _attribute_priority(member) > _attribute_priority(
            current
        ):
            members[member.name] = member

    return sorted(members.values(), key=lambda member: (member.name, member.lineno))


def _is_protocol_entity(
    protocol_entity: Entity,
    entities: Sequence[Entity],
    *,
    visited: set[str],
    lookup: ProtocolEntityLookup,
) -> bool:
    if protocol_entity.kind != "class":
        return False
    if protocol_entity.canonical_id in visited:
        return False

    visited.add(protocol_entity.canonical_id)
    base_refs = list(protocol_entity.extras.get("bases") or [])
    if not base_refs:
        return False

    if any(base_ref in _PROTOCOL_ROOT_REFERENCES for base_ref in base_refs):
        return True

    for base_ref in base_refs:
        base_entity = lookup.unique_class_by_fqn(str(base_ref))
        if base_entity is not None and _is_protocol_entity(
            base_entity, entities, visited=visited, lookup=lookup
        ):
            return True
    return False


def _property_setter_names(statements: Sequence[ast.stmt]) -> set[str]:
    names: set[str] = set()
    for stmt in statements:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in stmt.decorator_list:
            decorator_name = _decorator_ref_name(decorator)
            if decorator_name and decorator_name.endswith(".setter"):
                names.add(decorator_name.rsplit(".", 1)[0])
    return names


def _class_member_from_stmt(
    stmt: ast.stmt,
    *,
    property_setters: set[str],
) -> ProtocolAttribute | None:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if any(
            _decorator_ref_name(decorator) == "property"
            for decorator in stmt.decorator_list
        ):
            return ProtocolAttribute(
                name=stmt.name,
                annotation=(
                    ast.unparse(stmt.returns) if stmt.returns is not None else None
                ),
                kind="property",
                is_writable=stmt.name in property_setters,
                is_classvar_deferred=False,
                lineno=getattr(stmt, "lineno", 0),
            )
        return None

    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        annotation, is_classvar_deferred = _normalized_attribute_annotation(
            stmt.annotation
        )
        return ProtocolAttribute(
            name=stmt.target.id,
            annotation=annotation,
            kind="attribute",
            is_writable=True,
            is_classvar_deferred=is_classvar_deferred,
            lineno=getattr(stmt, "lineno", 0),
        )

    if isinstance(stmt, ast.Assign):
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            return None
        return ProtocolAttribute(
            name=stmt.targets[0].id,
            annotation=None,
            kind="attribute",
            is_writable=True,
            is_classvar_deferred=False,
            lineno=getattr(stmt, "lineno", 0),
        )

    return None


def _normalized_attribute_annotation(annotation: ast.AST) -> tuple[str, bool]:
    if isinstance(annotation, ast.Subscript):
        inner = classvar_inner_annotation(annotation)
        if inner is not None:
            return inner, True
    return safe_unparse(annotation), False


def _attribute_priority(member: ProtocolAttribute) -> tuple[int, int]:
    return (
        2 if member.kind == "property" else 1 if member.annotation else 0,
        -member.lineno,
    )


def _decorator_ref_name(node: ast.AST) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        base = dotted_name(target.value)
        if base:
            return f"{base}.{target.attr}"
        return target.attr
    return None


__all__ = [
    "ProtocolAttribute",
    "class_attributes",
    "class_methods",
    "declared_class_attributes",
    "declared_class_methods",
    "is_protocol_entity",
    "protocol_attributes",
    "protocol_methods",
]
