from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from pythonarchtesting.entities import Entity
from pythonarchtesting.protocols.attribute_introspection import (
    ResolvedAttribute,
    collect_attributes,
)

from .construction_resolution import constructor_candidates_for_class
from .member_name_resolution import (
    member_origin,
    target_methods_for_class,
)
from .signature_comparison import method_kind as resolved_method_kind

if TYPE_CHECKING:
    from pythonarchtesting.core.models import EvalContext


_SUPPORTED_DESCRIPTOR_KINDS = frozenset({"cached_property", "classproperty"})


@dataclass(frozen=True)
class SelectedMember:
    name: str
    member_kind: str
    qualname: str
    module_path: str
    lineno: int | None
    origin: str
    inherited: bool
    entity_id: str | None
    storage: str | None
    method_kind: str | None
    annotation: str | None
    descriptor_kind: str | None
    source: str


def _attribute_member_kind(attribute: ResolvedAttribute) -> str:
    if attribute.descriptor_kind:
        return "descriptor"
    if attribute.storage == "property":
        return "property"
    return "attribute"


def collect_method_members(
    target_class: Entity,
    ctx: "EvalContext",
    *,
    declared_only: bool,
    method_kind: str,
) -> list[SelectedMember]:
    methods = target_methods_for_class(
        target_class,
        ctx,
        include_inherited=not declared_only,
    )
    members: list[SelectedMember] = []
    for method in methods:
        actual_kind = resolved_method_kind(method)
        if method_kind != "any":
            if method_kind == "classmethod" and actual_kind != "class":
                continue
            if method_kind == "staticmethod" and actual_kind != "static":
                continue
            if method_kind == "instance" and actual_kind != "instance":
                continue
        origin = member_origin(method, target_class, ctx)
        members.append(
            SelectedMember(
                name=method.name,
                member_kind="method",
                qualname=method.qualname,
                module_path=method.module_path,
                lineno=method.lineno,
                origin=origin,
                inherited=origin == "inherited",
                entity_id=method.canonical_id,
                storage=None,
                method_kind=actual_kind,
                annotation=None,
                descriptor_kind=None,
                source="method",
            )
        )
    return members


def collect_attribute_members(
    target_class: Entity,
    ctx: "EvalContext",
    *,
    declared_only: bool,
    storage: str,
    allow_property: bool,
    descriptor_kinds: tuple[str, ...] | None,
    include_dynamic_attributes: bool,
    interpret_dataclass_fields: bool,
) -> list[SelectedMember]:
    include_descriptors = bool(descriptor_kinds)
    if include_descriptors:
        kinds_set: set[str] | None = {
            kind for kind in descriptor_kinds or () if kind in _SUPPORTED_DESCRIPTOR_KINDS
        }
        if not kinds_set:
            kinds_set = None
    else:
        kinds_set = None

    attribute_map = collect_attributes(
        target_class,
        ctx.target_index.all_sorted,
        include_inherited=not declared_only,
        include_instance=storage in {"any", "instance"},
        include_class=storage in {"any", "class"},
        include_properties=allow_property,
        include_descriptors=include_descriptors,
        include_dynamic_attributes=include_dynamic_attributes,
        descriptor_kinds=kinds_set,
        interpret_dataclass_fields=interpret_dataclass_fields,
    )

    members: list[SelectedMember] = []
    for name, candidates in attribute_map.items():
        if not candidates:
            continue
        attribute = candidates[0]
        members.append(
            SelectedMember(
                name=name,
                member_kind=_attribute_member_kind(attribute),
                qualname=attribute.declared_on_qualname + "." + name
                if attribute.declared_on_qualname
                else name,
                module_path=target_class.module_path,
                lineno=attribute.lineno,
                origin=attribute.origin,
                inherited=attribute.inherited,
                entity_id=attribute.declared_on_entity_id or None,
                storage=attribute.storage,
                method_kind=None,
                annotation=attribute.annotation,
                descriptor_kind=attribute.descriptor_kind,
                source="attribute",
            )
        )
    return members


def collect_constructor_members(
    target_class: Entity,
    ctx: "EvalContext",
    *,
    declared_only: bool,
    constructor_kind: str,
    include_dataclass_constructor: bool,
) -> list[SelectedMember]:
    candidates = constructor_candidates_for_class(
        target_class,
        ctx.target_index.all_sorted,
        allow_inherited=not declared_only,
    )

    members: list[SelectedMember] = []
    for candidate in candidates:
        if constructor_kind != "auto" and candidate.kind != constructor_kind:
            continue
        if (
            not include_dataclass_constructor
            and candidate.origin == "generated_dataclass_init"
        ):
            continue
        entity = candidate.entity
        members.append(
            SelectedMember(
                name=candidate.kind,
                member_kind="constructor",
                qualname=entity.qualname,
                module_path=entity.module_path,
                lineno=entity.lineno,
                origin=candidate.origin,
                inherited=candidate.inherited,
                entity_id=entity.canonical_id,
                storage=None,
                method_kind=None,
                annotation=None,
                descriptor_kind=None,
                source="constructor",
            )
        )
    return members


def filter_members_by_name_match(
    members: Iterable[SelectedMember],
    *,
    name_match: str,
    names: list[str] | None,
    pattern: str | None,
) -> list[SelectedMember]:
    members_list = list(members)
    if name_match == "any":
        return members_list
    if name_match == "regex":
        if pattern is None:
            return []
        return [member for member in members_list if re.fullmatch(pattern, member.name)]
    if name_match == "names":
        accepted = {name for name in names or [] if name}
        if not accepted:
            return []
        return [member for member in members_list if member.name in accepted]
    return []


__all__ = [
    "SelectedMember",
    "collect_attribute_members",
    "collect_constructor_members",
    "collect_method_members",
    "filter_members_by_name_match",
]
