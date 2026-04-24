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
    "descriptor_assign",
    "descriptor_assign_property",
    "descriptor_assign_cached_property",
    "descriptor_assign_classproperty",
    "dynamic_setattr_class",
    "dynamic_setattr_instance",
    "property",
    "cached_property",
    "classproperty",
    "self_annassign",
    "self_assign",
    "dataclass_field",
]

_SUPPORTED_DESCRIPTOR_KINDS = {"cached_property", "classproperty"}


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
    descriptor_kind: str | None = None


@dataclass(frozen=True)
class _DynamicReceiver:
    name: str
    storage: Literal["instance", "class"]
    origin: Literal["dynamic_setattr_instance", "dynamic_setattr_class"]


@dataclass(frozen=True)
class _DescriptorSpec:
    storage: AttributeStorage
    origin: AttributeOrigin
    descriptor_kind: str | None
    is_writable: bool


def direct_declared_class_attributes(
    class_entity: Entity,
    entities: Sequence[Entity] | None = None,
    *,
    include_descriptors: bool = False,
) -> list[ResolvedAttribute]:
    node = class_entity.extras.get("ast_node")
    if class_entity.kind != "class" or not isinstance(node, ast.ClassDef):
        return []

    members: dict[str, ResolvedAttribute] = {}
    for stmt in node.body:
        member = _class_attribute_from_stmt(
            stmt,
            class_entity=class_entity,
            entities=entities,
            include_descriptors=include_descriptors,
        )
        if member is None:
            continue
        _store_preferred_member(members, member)

    return sorted(members.values(), key=lambda member: (member.name, member.lineno))


def direct_declared_descriptor_attributes(
    class_entity: Entity,
    *,
    include_property: bool,
    descriptor_kinds: set[str] | None = None,
) -> list[ResolvedAttribute]:
    node = class_entity.extras.get("ast_node")
    if class_entity.kind != "class" or not isinstance(node, ast.ClassDef):
        return []

    requested_kinds = set(descriptor_kinds or set()) & _SUPPORTED_DESCRIPTOR_KINDS
    setter_names = _property_setter_names(node)

    members: dict[str, ResolvedAttribute] = {}
    for stmt in node.body:
        member = _decorated_descriptor_attribute_from_stmt(
            stmt,
            class_entity=class_entity,
            setter_names=setter_names,
            include_property=include_property,
            descriptor_kinds=requested_kinds,
        )
        if member is not None:
            _store_preferred_member(members, member)
            continue

        member = _assigned_descriptor_attribute_from_stmt(
            stmt,
            class_entity=class_entity,
            include_property=include_property,
            descriptor_kinds=requested_kinds,
        )
        if member is not None:
            _store_preferred_member(members, member)

    return sorted(members.values(), key=lambda member: (member.name, member.lineno))


def direct_declared_property_attributes(
    class_entity: Entity,
) -> list[ResolvedAttribute]:
    return [
        member
        for member in direct_declared_descriptor_attributes(
            class_entity,
            include_property=True,
            descriptor_kinds=set(),
        )
        if member.storage == "property" and member.descriptor_kind is None
    ]


def direct_declared_instance_attributes(
    class_entity: Entity,
    entities: Sequence[Entity],
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
        collector = _AssignedInstanceAttributeCollector(
            receiver_name=receiver_name,
            class_entity=class_entity,
        )
        for stmt in node.body:
            collector.visit(stmt)
        for member in collector.members.values():
            _store_preferred_member(members, member)

    return sorted(members.values(), key=lambda member: (member.name, member.lineno))


def direct_declared_dataclass_fields(class_entity: Entity) -> list[ResolvedAttribute]:
    node = class_entity.extras.get("ast_node")
    if class_entity.kind != "class" or not isinstance(node, ast.ClassDef):
        return []
    if not _is_dataclass_class(node):
        return []

    members: dict[str, ResolvedAttribute] = {}
    for stmt in node.body:
        member = _dataclass_field_from_stmt(stmt, class_entity=class_entity)
        if member is None:
            continue
        _store_preferred_member(members, member)

    return sorted(members.values(), key=lambda member: (member.name, member.lineno))


def direct_declared_dynamic_attributes(
    class_entity: Entity,
    entities: Sequence[Entity],
) -> list[ResolvedAttribute]:
    if class_entity.kind != "class":
        return []

    members: dict[str, ResolvedAttribute] = {}
    for method in _direct_class_methods(class_entity, entities):
        receiver = _dynamic_receiver(method)
        if receiver is None:
            continue
        node = method.extras.get("ast_node")
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        collector = _DynamicAttributeCollector(
            receiver=receiver,
            class_entity=class_entity,
        )
        for stmt in node.body:
            collector.visit(stmt)
        for member in collector.members.values():
            _store_preferred_member(members, member)

    return sorted(members.values(), key=lambda member: (member.name, member.lineno))


def collect_attributes(
    class_entity: Entity,
    entities: Sequence[Entity],
    *,
    include_inherited: bool,
    include_instance: bool,
    include_class: bool,
    include_properties: bool,
    include_descriptors: bool = False,
    include_dynamic_attributes: bool = False,
    descriptor_kinds: set[str] | None = None,
    interpret_dataclass_fields: bool = False,
) -> dict[str, list[ResolvedAttribute]]:
    lookup = ProtocolEntityLookup.from_entities(entities)
    return _collect_attributes(
        class_entity,
        entities,
        include_inherited=include_inherited,
        include_instance=include_instance,
        include_class=include_class,
        include_properties=include_properties,
        include_descriptors=include_descriptors,
        include_dynamic_attributes=include_dynamic_attributes,
        descriptor_kinds=set(descriptor_kinds or set()),
        interpret_dataclass_fields=interpret_dataclass_fields,
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
    include_descriptors: bool,
    include_dynamic_attributes: bool,
    descriptor_kinds: set[str],
    interpret_dataclass_fields: bool,
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
                include_descriptors=include_descriptors,
                include_dynamic_attributes=include_dynamic_attributes,
                descriptor_kinds=descriptor_kinds,
                interpret_dataclass_fields=interpret_dataclass_fields,
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
        class_members = direct_declared_class_attributes(
            class_entity,
            entities,
            include_descriptors=include_descriptors,
        )
        if interpret_dataclass_fields:
            initvar_names = _dataclass_initvar_names(class_entity)
            class_members = [
                member for member in class_members if member.name not in initvar_names
            ]
        local_members.extend(class_members)
    if include_instance:
        local_members.extend(
            direct_declared_instance_attributes(class_entity, entities)
        )
        if interpret_dataclass_fields:
            local_members.extend(direct_declared_dataclass_fields(class_entity))
    if include_properties or descriptor_kinds:
        local_members.extend(
            direct_declared_descriptor_attributes(
                class_entity,
                include_property=include_properties,
                descriptor_kinds=descriptor_kinds,
            )
        )
    if include_dynamic_attributes:
        local_members.extend(direct_declared_dynamic_attributes(class_entity, entities))

    for member in local_members:
        collected.setdefault(member.name, []).append(member)

    return {
        name: sorted(members, key=_attribute_priority)
        for name, members in sorted(collected.items())
    }


def _class_attribute_from_stmt(
    stmt: ast.stmt,
    *,
    class_entity: Entity,
    entities: Sequence[Entity] | None,
    include_descriptors: bool,
) -> ResolvedAttribute | None:
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        if _skip_class_attribute_name(stmt.target.id):
            return None
        if _is_descriptor_assignment(
            stmt.value,
            entities=entities,
            module_path=class_entity.module_path,
        ):
            if not include_descriptors:
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
                origin="descriptor_assign",
            )
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
        if _is_descriptor_assignment(
            stmt.value,
            entities=entities,
            module_path=class_entity.module_path,
        ):
            if not include_descriptors:
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
                origin="descriptor_assign",
            )
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


def _decorated_descriptor_attribute_from_stmt(
    stmt: ast.stmt,
    *,
    class_entity: Entity,
    setter_names: set[str],
    include_property: bool,
    descriptor_kinds: set[str],
) -> ResolvedAttribute | None:
    if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None

    for decorator in stmt.decorator_list:
        spec = _decorator_descriptor_spec(decorator)
        if spec is None:
            continue
        if spec.descriptor_kind is None and not include_property:
            continue
        if (
            spec.descriptor_kind is not None
            and spec.descriptor_kind not in descriptor_kinds
        ):
            continue

        is_writable = spec.is_writable
        if spec.origin == "property":
            is_writable = stmt.name in setter_names

        return ResolvedAttribute(
            name=stmt.name,
            annotation=safe_unparse(stmt.returns) or None,
            storage=spec.storage,
            lineno=getattr(stmt, "lineno", 0),
            declared_on_entity_id=class_entity.canonical_id,
            declared_on_qualname=class_entity.qualname,
            inherited=False,
            is_writable=is_writable,
            origin=spec.origin,
            descriptor_kind=spec.descriptor_kind,
        )

    return None


def _assigned_descriptor_attribute_from_stmt(
    stmt: ast.stmt,
    *,
    class_entity: Entity,
    include_property: bool,
    descriptor_kinds: set[str],
) -> ResolvedAttribute | None:
    target_name: str | None = None
    annotation: str | None = None
    value: ast.AST | None = None

    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        if _skip_class_attribute_name(stmt.target.id):
            return None
        target_name = stmt.target.id
        annotation = _normalized_attribute_annotation(stmt.annotation)
        value = stmt.value
    elif isinstance(stmt, ast.Assign):
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            return None
        if _skip_class_attribute_name(stmt.targets[0].id):
            return None
        target_name = stmt.targets[0].id
        value = stmt.value
    else:
        return None

    spec = _assigned_descriptor_spec(value)
    if spec is None or target_name is None:
        return None
    if spec.descriptor_kind is None and not include_property:
        return None
    if (
        spec.descriptor_kind is not None
        and spec.descriptor_kind not in descriptor_kinds
    ):
        return None

    return ResolvedAttribute(
        name=target_name,
        annotation=annotation,
        storage=spec.storage,
        lineno=getattr(stmt, "lineno", 0),
        declared_on_entity_id=class_entity.canonical_id,
        declared_on_qualname=class_entity.qualname,
        inherited=False,
        is_writable=spec.is_writable,
        origin=spec.origin,
        descriptor_kind=spec.descriptor_kind,
    )


def _dataclass_field_from_stmt(
    stmt: ast.stmt,
    *,
    class_entity: Entity,
) -> ResolvedAttribute | None:
    if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
        return None
    if _skip_class_attribute_name(stmt.target.id):
        return None
    if _is_classvar_annotation(stmt.annotation) or _is_initvar_annotation(
        stmt.annotation
    ):
        return None

    return ResolvedAttribute(
        name=stmt.target.id,
        annotation=safe_unparse(stmt.annotation) or None,
        storage="instance",
        lineno=getattr(stmt, "lineno", 0),
        declared_on_entity_id=class_entity.canonical_id,
        declared_on_qualname=class_entity.qualname,
        inherited=False,
        is_writable=True,
        origin="dataclass_field",
    )


class _AssignedInstanceAttributeCollector(ast.NodeVisitor):
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
        _store_preferred_member(self.members, member)


class _DynamicAttributeCollector(ast.NodeVisitor):
    def __init__(self, *, receiver: _DynamicReceiver, class_entity: Entity) -> None:
        self.receiver = receiver
        self.class_entity = class_entity
        self.members: dict[str, ResolvedAttribute] = {}

    def visit_Call(self, node: ast.Call) -> None:
        if not (
            isinstance(node.func, ast.Name)
            and node.func.id == "setattr"
            and len(node.args) >= 3
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == self.receiver.name
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            self.generic_visit(node)
            return

        self._store(
            ResolvedAttribute(
                name=node.args[1].value,
                annotation=None,
                storage=self.receiver.storage,
                lineno=getattr(node, "lineno", 0),
                declared_on_entity_id=self.class_entity.canonical_id,
                declared_on_qualname=self.class_entity.qualname,
                inherited=False,
                is_writable=True,
                origin=self.receiver.origin,
            )
        )
        for argument in node.args[2:]:
            self.visit(argument)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return None

    def _store(self, member: ResolvedAttribute) -> None:
        _store_preferred_member(self.members, member)


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


def _dynamic_receiver(method: Entity) -> _DynamicReceiver | None:
    node = method.extras.get("ast_node")
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    positional_args = [*node.args.posonlyargs, *node.args.args]
    if not positional_args:
        return None

    method_kind = str(method.surface_meta.get("method_kind") or "")
    if method_kind == "class":
        return _DynamicReceiver(
            name=positional_args[0].arg,
            storage="class",
            origin="dynamic_setattr_class",
        )
    if method_kind == "static":
        return None
    return _DynamicReceiver(
        name=positional_args[0].arg,
        storage="instance",
        origin="dynamic_setattr_instance",
    )


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


def _attribute_priority(member: ResolvedAttribute) -> tuple[int, int, int, int, int]:
    return (
        0 if not member.inherited else 1,
        _member_category_priority(member),
        0 if member.annotation is not None else 1,
        0 if member.storage != "property" else 1,
        member.lineno,
    )


def _member_category_priority(member: ResolvedAttribute) -> int:
    if member.origin in {"dynamic_setattr_instance", "dynamic_setattr_class"}:
        return 2
    if member.storage == "property" or member.descriptor_kind is not None:
        return 1
    return 0


def _store_preferred_member(
    members: dict[str, ResolvedAttribute],
    member: ResolvedAttribute,
) -> None:
    current = members.get(member.name)
    if current is None or _attribute_priority(member) < _attribute_priority(current):
        members[member.name] = member


def _property_setter_names(node: ast.ClassDef) -> set[str]:
    setter_names: set[str] = set()
    for stmt in node.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in stmt.decorator_list:
            ref = _decorator_ref_name(decorator)
            if ref is not None and ref.endswith(".setter"):
                setter_names.add(ref[: -len(".setter")])
    return setter_names


def _decorator_descriptor_spec(node: ast.AST) -> _DescriptorSpec | None:
    ref = _decorator_ref_name(node)
    return _descriptor_spec_from_ref(ref, assignment=False)


def _assigned_descriptor_spec(node: ast.AST | None) -> _DescriptorSpec | None:
    if not isinstance(node, ast.Call):
        return None
    ref = _dotted_name(node.func)
    return _descriptor_spec_from_ref(ref, assignment=True)


def _descriptor_spec_from_ref(
    ref: str | None,
    *,
    assignment: bool,
) -> _DescriptorSpec | None:
    if ref is None:
        return None

    if ref == "property":
        return _DescriptorSpec(
            storage="property",
            origin="descriptor_assign_property" if assignment else "property",
            descriptor_kind=None,
            is_writable=False,
        )

    if ref in {"cached_property", "functools.cached_property"}:
        return _DescriptorSpec(
            storage="property",
            origin=(
                "descriptor_assign_cached_property" if assignment else "cached_property"
            ),
            descriptor_kind="cached_property",
            is_writable=False,
        )

    if ref.rsplit(".", 1)[-1] == "classproperty":
        return _DescriptorSpec(
            storage="class",
            origin=(
                "descriptor_assign_classproperty" if assignment else "classproperty"
            ),
            descriptor_kind="classproperty",
            is_writable=False,
        )

    return None


def _is_dataclass_class(node: ast.ClassDef) -> bool:
    return any(
        (_decorator_ref_name(decorator) in {"dataclass", "dataclasses.dataclass"})
        for decorator in node.decorator_list
    )


def _dataclass_initvar_names(class_entity: Entity) -> set[str]:
    node = class_entity.extras.get("ast_node")
    if class_entity.kind != "class" or not isinstance(node, ast.ClassDef):
        return set()
    if not _is_dataclass_class(node):
        return set()

    names: set[str] = set()
    for stmt in node.body:
        if (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and _is_initvar_annotation(stmt.annotation)
        ):
            names.add(stmt.target.id)
    return names


def _is_classvar_annotation(annotation: ast.AST) -> bool:
    return (
        isinstance(annotation, ast.Subscript)
        and classvar_inner_annotation(annotation) is not None
    )


def _is_initvar_annotation(annotation: ast.AST) -> bool:
    if not isinstance(annotation, ast.Subscript):
        return False
    container = _dotted_name(annotation.value)
    return container in {"InitVar", "dataclasses.InitVar"}


def _descriptor_class_names(
    entities: Sequence[Entity] | None,
    *,
    module_path: str,
) -> set[str]:
    if entities is None:
        return set()
    names: set[str] = set()
    for entity in entities:
        if entity.kind != "class" or entity.module_path != module_path:
            continue
        node = entity.extras.get("ast_node")
        if not isinstance(node, ast.ClassDef):
            continue
        method_names = {
            stmt.name
            for stmt in node.body
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if {"__get__", "__set__", "__delete__"} & method_names:
            names.add(entity.name)
            names.add(entity.qualname)
    return names


def _is_descriptor_assignment(
    value: ast.AST | None,
    *,
    entities: Sequence[Entity] | None,
    module_path: str,
) -> bool:
    if not isinstance(value, ast.Call):
        return False
    ref = _dotted_name(value.func)
    if not ref:
        return False
    terminal = ref.rsplit(".", 1)[-1]
    if terminal.endswith("Descriptor"):
        return True
    return terminal in _descriptor_class_names(entities, module_path=module_path)


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
    "direct_declared_dataclass_fields",
    "direct_declared_descriptor_attributes",
    "direct_declared_dynamic_attributes",
    "direct_declared_instance_attributes",
    "direct_declared_property_attributes",
]
