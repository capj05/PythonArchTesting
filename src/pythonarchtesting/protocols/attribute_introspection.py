from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from typing import Literal, Sequence

from pythonarchtesting.entities import Entity
from pythonarchtesting.protocols.entity_lookup import ProtocolEntityLookup
from pythonarchtesting.protocols.type_expr import (
    classvar_inner_annotation,
    safe_unparse,
)

AttributeStorage = Literal["instance", "class", "property"]
AttributeOrigin = Literal[
    "class_annassign",
    "class_assign",
    "self_annassign",
    "self_assign",
    "property",
]


@dataclass(frozen=True)
class ResolvedAttribute:
    name: str
    annotation: str | None
    storage: AttributeStorage
    lineno: int
    declared_on_entity_id: str
    declared_on_qualname: str
    inherited: bool
    is_writable: bool
    origin: AttributeOrigin


def direct_declared_class_attributes(class_entity: Entity) -> list[ResolvedAttribute]:
    node = class_entity.extras.get("ast_node")
    if class_entity.kind != "class" or not isinstance(node, ast.ClassDef):
        return []

    members: dict[str, ResolvedAttribute] = {}
    for stmt in node.body:
        member = _class_attribute_from_stmt(stmt, class_entity)
        if member is None:
            continue
        current = members.get(member.name)
        if current is None or _attribute_priority(member) < _attribute_priority(
            current
        ):
            members[member.name] = member

    return sorted(members.values(), key=lambda member: (member.name, member.lineno))


def direct_declared_property_attributes(
    class_entity: Entity,
) -> list[ResolvedAttribute]:
    node = class_entity.extras.get("ast_node")
    if class_entity.kind != "class" or not isinstance(node, ast.ClassDef):
        return []

    # First pass: collect setter names — any method with @<name>.setter decorator
    setter_names: set[str] = set()
    for stmt in node.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in stmt.decorator_list:
            ref = _decorator_ref_name(decorator)
            if ref is not None and ref.endswith(".setter"):
                setter_names.add(ref[: -len(".setter")])

    members: dict[str, ResolvedAttribute] = {}
    for stmt in node.body:
        member = _property_attribute_from_stmt(
            stmt, class_entity=class_entity, setter_names=setter_names
        )
        if member is None:
            continue
        current = members.get(member.name)
        if current is None or _attribute_priority(member) < _attribute_priority(
            current
        ):
            members[member.name] = member

    return sorted(members.values(), key=lambda member: (member.name, member.lineno))


def direct_declared_instance_attributes(
    class_entity: Entity, entities: Sequence[Entity]
) -> list[ResolvedAttribute]:
    if class_entity.kind != "class":
        return []

    members: dict[str, ResolvedAttribute] = {}
    for method in _direct_class_methods(class_entity, entities):
        receiver_name = _instance_receiver_name(method)
        if receiver_name is None:
            continue
        node = method.extras.get("ast_node")
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        collector = _InstanceAttributeCollector(
            receiver_name=receiver_name,
            class_entity=class_entity,
        )
        for stmt in node.body:
            collector.visit(stmt)
        for member in collector.members.values():
            current = members.get(member.name)
            if current is None or _attribute_priority(member) < _attribute_priority(
                current
            ):
                members[member.name] = member

    return sorted(members.values(), key=lambda member: (member.name, member.lineno))


def collect_attributes(
    class_entity: Entity,
    entities: Sequence[Entity],
    *,
    include_inherited: bool,
    include_instance: bool,
    include_class: bool,
    include_properties: bool,
) -> dict[str, list[ResolvedAttribute]]:
    lookup = ProtocolEntityLookup.from_entities(entities)
    return _collect_attributes(
        class_entity,
        entities,
        include_inherited=include_inherited,
        include_instance=include_instance,
        include_class=include_class,
        include_properties=include_properties,
        lookup=lookup,
        visited=set(),
    )


def _collect_attributes(
    class_entity: Entity,
    entities: Sequence[Entity],
    *,
    include_inherited: bool,
    include_instance: bool,
    include_class: bool,
    include_properties: bool,
    lookup: ProtocolEntityLookup,
    visited: set[str],
) -> dict[str, list[ResolvedAttribute]]:
    if class_entity.kind != "class" or class_entity.canonical_id in visited:
        return {}

    visited.add(class_entity.canonical_id)
    collected: dict[str, list[ResolvedAttribute]] = {}

    if include_inherited:
        for base_entity in lookup.resolved_bases(class_entity):
            base_members = _collect_attributes(
                base_entity,
                entities,
                include_inherited=True,
                include_instance=include_instance,
                include_class=include_class,
                include_properties=include_properties,
                lookup=lookup,
                visited=visited,
            )
            for name, members in base_members.items():
                inherited_members = [
                    replace(member, inherited=True) for member in members
                ]
                collected.setdefault(name, []).extend(inherited_members)

    local_members: list[ResolvedAttribute] = []
    if include_class:
        local_members.extend(direct_declared_class_attributes(class_entity))
    if include_instance:
        local_members.extend(
            direct_declared_instance_attributes(class_entity, entities)
        )
    if include_properties:
        local_members.extend(direct_declared_property_attributes(class_entity))

    for member in local_members:
        collected.setdefault(member.name, []).append(member)

    return {
        name: sorted(members, key=_attribute_priority)
        for name, members in sorted(collected.items())
    }


def _class_attribute_from_stmt(
    stmt: ast.stmt, class_entity: Entity
) -> ResolvedAttribute | None:
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        if _skip_class_attribute_name(stmt.target.id):
            return None
        return ResolvedAttribute(
            name=stmt.target.id,
            annotation=_normalized_attribute_annotation(stmt.annotation),
            storage="class",
            lineno=getattr(stmt, "lineno", 0),
            declared_on_entity_id=class_entity.canonical_id,
            declared_on_qualname=class_entity.qualname,
            inherited=False,
            is_writable=True,
            origin="class_annassign",
        )

    if isinstance(stmt, ast.Assign):
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            return None
        name = stmt.targets[0].id
        if _skip_class_attribute_name(name):
            return None
        return ResolvedAttribute(
            name=name,
            annotation=None,
            storage="class",
            lineno=getattr(stmt, "lineno", 0),
            declared_on_entity_id=class_entity.canonical_id,
            declared_on_qualname=class_entity.qualname,
            inherited=False,
            is_writable=True,
            origin="class_assign",
        )

    return None


def _property_attribute_from_stmt(
    stmt: ast.stmt,
    *,
    class_entity: Entity,
    setter_names: set[str],
) -> ResolvedAttribute | None:
    if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    if not any(
        _decorator_ref_name(decorator) == "property"
        for decorator in stmt.decorator_list
    ):
        return None
    is_writable = stmt.name in setter_names
    return ResolvedAttribute(
        name=stmt.name,
        annotation=safe_unparse(stmt.returns) or None,
        storage="property",
        lineno=getattr(stmt, "lineno", 0),
        declared_on_entity_id=class_entity.canonical_id,
        declared_on_qualname=class_entity.qualname,
        inherited=False,
        is_writable=is_writable,
        origin="property",
    )


class _InstanceAttributeCollector(ast.NodeVisitor):
    def __init__(self, *, receiver_name: str, class_entity: Entity) -> None:
        self.receiver_name = receiver_name
        self.class_entity = class_entity
        self.members: dict[str, ResolvedAttribute] = {}

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            name = _receiver_attribute_name(target, receiver_name=self.receiver_name)
            if name is None:
                continue
            self._store(
                ResolvedAttribute(
                    name=name,
                    annotation=None,
                    storage="instance",
                    lineno=getattr(node, "lineno", 0),
                    declared_on_entity_id=self.class_entity.canonical_id,
                    declared_on_qualname=self.class_entity.qualname,
                    inherited=False,
                    is_writable=True,
                    origin="self_assign",
                )
            )
        self.generic_visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        name = _receiver_attribute_name(node.target, receiver_name=self.receiver_name)
        if name is not None:
            self._store(
                ResolvedAttribute(
                    name=name,
                    annotation=safe_unparse(node.annotation) or None,
                    storage="instance",
                    lineno=getattr(node, "lineno", 0),
                    declared_on_entity_id=self.class_entity.canonical_id,
                    declared_on_qualname=self.class_entity.qualname,
                    inherited=False,
                    is_writable=True,
                    origin="self_annassign",
                )
            )
        if node.value is not None:
            self.generic_visit(node.value)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return None

    def _store(self, member: ResolvedAttribute) -> None:
        current = self.members.get(member.name)
        if current is None or _attribute_priority(member) < _attribute_priority(
            current
        ):
            self.members[member.name] = member


def _direct_class_methods(
    class_entity: Entity, entities: Sequence[Entity]
) -> list[Entity]:
    prefix = f"{class_entity.qualname}."
    methods = [
        candidate
        for candidate in entities
        if candidate.module_path == class_entity.module_path
        and candidate.kind == "method"
        and candidate.qualname.startswith(prefix)
        and not bool(candidate.surface_meta.get("property"))
    ]
    methods.sort(
        key=lambda candidate: (candidate.name, candidate.qualname, candidate.lineno)
    )
    return methods


def _instance_receiver_name(method: Entity) -> str | None:
    if method.surface_meta.get("method_kind") in {"class", "static"}:
        return None
    node = method.extras.get("ast_node")
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    positional_args = [*node.args.posonlyargs, *node.args.args]
    if not positional_args:
        return None
    return positional_args[0].arg


def _receiver_attribute_name(target: ast.AST, *, receiver_name: str) -> str | None:
    if not isinstance(target, ast.Attribute):
        return None
    if not isinstance(target.value, ast.Name) or target.value.id != receiver_name:
        return None
    return target.attr


def _normalized_attribute_annotation(annotation: ast.AST) -> str | None:
    if isinstance(annotation, ast.Subscript):
        inner = classvar_inner_annotation(annotation)
        if inner is not None:
            return inner
    rendered = safe_unparse(annotation)
    return rendered or None


def _skip_class_attribute_name(name: str) -> bool:
    if name == "__archtest__":
        return True
    return name.startswith("__") and name.endswith("__")


def _attribute_priority(member: ResolvedAttribute) -> tuple[int, int, int, int]:
    return (
        0 if not member.inherited else 1,
        0 if member.annotation is not None else 1,
        0 if member.storage != "property" else 1,
        member.lineno,
    )


def _decorator_ref_name(node: ast.AST) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        base = _dotted_name(target.value)
        if base:
            return f"{base}.{target.attr}"
        return target.attr
    return None


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        if base:
            return f"{base}.{node.attr}"
        return node.attr
    return None


__all__ = [
    "ResolvedAttribute",
    "collect_attributes",
    "direct_declared_class_attributes",
    "direct_declared_instance_attributes",
    "direct_declared_property_attributes",
]
