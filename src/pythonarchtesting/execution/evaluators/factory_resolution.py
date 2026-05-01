from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pythonarchtesting.entities import Entity, build_canonical_id
from pythonarchtesting.protocols.entity_lookup import ProtocolEntityLookup

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
_ASSIGNMENT_FACTORY_WRAPPERS = {
    "classmethod": "class",
    "staticmethod": "static",
}


@dataclass(frozen=True)
class StaticAttributeFactoryCandidate:
    name: str
    owner_class: Entity
    target_class: Entity
    lineno: int
    annotation: str | None
    value_expr: str | None
    inherited: bool


def factory_kind(entity: Entity, *, detection_mode: str = "strict") -> str:
    from pythonarchtesting.execution.evaluators.api_signature import _method_kind

    if entity.name in _FACTORY_CONSTRUCTOR_NAMES:
        return "constructor"
    kind = _method_kind(entity, detection_mode=detection_mode)
    if kind == "class":
        return "classmethod"
    if kind == "static":
        return "staticmethod"
    return "unknown"


def _is_factory_candidate(entity: Entity, *, detection_mode: str) -> bool:
    return factory_kind(entity, detection_mode=detection_mode) != "unknown"


def _decorator_ref_name(node: ast.AST) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        try:
            return ast.unparse(target)
        except Exception:
            return target.attr
    return None


def _assignment_method_kind(value: ast.AST) -> str | None:
    if not isinstance(value, ast.Call) or len(value.args) != 1 or value.keywords:
        return None
    ref_name = _decorator_ref_name(value.func)
    if ref_name is None:
        return None
    return _ASSIGNMENT_FACTORY_WRAPPERS.get(ref_name.rsplit(".", 1)[-1])


def _safe_unparse(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _is_dunder_name(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _synthetic_assignment_factory_candidate(
    method: Entity,
    *,
    alias_name: str,
    method_kind: str,
    owner_class: Entity,
    lineno: int,
) -> Entity:
    qualname = f"{owner_class.qualname}.{alias_name}"
    decorators_meta = dict(method.decorators_meta)
    decorators_meta["method_kind"] = method_kind
    extras = dict(method.extras)
    extras["synthetic_factory_assignment"] = True
    extras["synthetic_factory_owner_id"] = owner_class.canonical_id
    extras["synthetic_factory_assignment_name"] = alias_name
    extras["synthetic_factory_assignment_lineno"] = lineno
    canonical_id = (
        build_canonical_id(
            method.role,
            method.root_label,
            method.module_path,
            qualname,
            method.kind,
            method.signature_key,
        )
        + f"#factory-{method_kind}"
    )
    return Entity(
        role=method.role,
        kind=method.kind,
        root_label=method.root_label,
        module_path=method.module_path,
        qualname=qualname,
        name=alias_name,
        filepath_rel=method.filepath_rel,
        lineno=lineno,
        signature=method.signature,
        signature_key=method.signature_key,
        ast_fingerprint=method.ast_fingerprint,
        source_hash=method.source_hash,
        doc_hash=method.doc_hash,
        decorators_meta=decorators_meta,
        canonical_id=canonical_id,
        annotation_declarations=list(method.annotation_declarations),
        extras=extras,
    )


def _declared_assignment_factory_candidates(
    owner_class: Entity,
    ctx: EvalContext,
) -> list[Entity]:
    node = owner_class.extras.get("ast_node")
    if not isinstance(node, ast.ClassDef):
        return []

    declared_methods = {
        method.name: method
        for method in target_methods_for_class(
            owner_class,
            ctx,
            include_inherited=False,
        )
    }

    candidates: dict[str, Entity] = {}
    for stmt in node.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            continue
        assignment_name = stmt.targets[0].id
        method_kind = _assignment_method_kind(stmt.value)
        if method_kind is None:
            continue
        wrapped = stmt.value.args[0]
        if not isinstance(wrapped, ast.Name):
            continue
        wrapped_method = declared_methods.get(wrapped.id)
        if wrapped_method is None:
            continue
        candidates[assignment_name] = _synthetic_assignment_factory_candidate(
            wrapped_method,
            alias_name=assignment_name,
            method_kind=method_kind,
            owner_class=owner_class,
            lineno=getattr(stmt, "lineno", wrapped_method.lineno),
        )
    return sorted(
        candidates.values(),
        key=lambda candidate: (candidate.name, candidate.qualname, candidate.lineno),
    )


def _candidate_owner_classes(
    target_class: Entity,
    ctx: EvalContext,
    *,
    include_inherited: bool,
) -> list[Entity]:
    if not include_inherited:
        return [target_class]

    lookup = ProtocolEntityLookup.from_entities(ctx.target_index.all_sorted)
    ordered: list[Entity] = []
    visited: set[str] = set()

    def visit(candidate_class: Entity) -> None:
        if candidate_class.canonical_id in visited:
            return
        visited.add(candidate_class.canonical_id)
        for base_class in lookup.resolved_bases(candidate_class):
            visit(base_class)
        ordered.append(candidate_class)

    visit(target_class)
    return ordered


def factory_candidates_for_class(
    target_class: Entity,
    ctx: EvalContext,
    *,
    allow_inherited: bool,
    detection_mode: str = "strict",
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
    method_candidates = {
        method.name: method
        for method in target_methods_for_class(
            target_class,
            ctx,
            include_inherited=allow_inherited,
        )
        if _is_factory_candidate(method, detection_mode=detection_mode)
        and method.name not in _FACTORY_CONSTRUCTOR_NAMES
        and not method.extras.get("assignment_wrapped_by")
    }
    if detection_mode == "extended":
        for owner_class in _candidate_owner_classes(
            target_class,
            ctx,
            include_inherited=allow_inherited,
        ):
            for candidate in _declared_assignment_factory_candidates(owner_class, ctx):
                method_candidates[candidate.name] = candidate
    return [
        *constructor_entities,
        *sorted(
            method_candidates.values(),
            key=lambda candidate: (candidate.name, candidate.qualname, candidate.lineno),
        ),
    ]


def static_attribute_factory_candidates_for_class(
    target_class: Entity,
    ctx: EvalContext,
    *,
    allow_inherited: bool,
) -> list[StaticAttributeFactoryCandidate]:
    candidates: dict[str, StaticAttributeFactoryCandidate] = {}
    for owner_class in _candidate_owner_classes(
        target_class,
        ctx,
        include_inherited=allow_inherited,
    ):
        node = owner_class.extras.get("ast_node")
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            name: str | None = None
            annotation: str | None = None
            value: ast.AST | None = None
            lineno = getattr(stmt, "lineno", owner_class.lineno)
            if isinstance(stmt, ast.Assign):
                if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                    continue
                name = stmt.targets[0].id
                value = stmt.value
            elif isinstance(stmt, ast.AnnAssign):
                if stmt.simple != 1 or not isinstance(stmt.target, ast.Name):
                    continue
                name = stmt.target.id
                annotation = _safe_unparse(stmt.annotation)
                value = stmt.value
            else:
                continue

            if name == "__archtest__" or _is_dunder_name(name):
                continue
            if value is not None and _assignment_method_kind(value) is not None:
                continue

            candidates[name] = StaticAttributeFactoryCandidate(
                name=name,
                owner_class=owner_class,
                target_class=target_class,
                lineno=lineno,
                annotation=annotation,
                value_expr=_safe_unparse(value),
                inherited=owner_class.canonical_id != target_class.canonical_id,
            )

    return sorted(
        candidates.values(),
        key=lambda candidate: (
            candidate.name,
            candidate.owner_class.qualname,
            candidate.lineno,
        ),
    )


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
    synthetic_owner_id = entity.extras.get("synthetic_factory_owner_id")
    if synthetic_owner_id is not None:
        return (
            "declared"
            if str(synthetic_owner_id) == target_class.canonical_id
            else "inherited"
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
    detection_mode: str = "strict",
) -> list[Entity]:
    result: list[Entity] = []
    for candidate in candidates:
        candidate_kind = factory_kind(candidate, detection_mode=detection_mode)
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


def filter_static_attribute_factory_candidates(
    candidates: list[StaticAttributeFactoryCandidate],
    *,
    name_match: str,
    source_name: str,
    aliases: list[str] | None,
    pattern: str | None,
) -> list[StaticAttributeFactoryCandidate]:
    result: list[StaticAttributeFactoryCandidate] = []
    for candidate in candidates:
        if name_match == "exact" and candidate.name == source_name:
            result.append(candidate)
        elif name_match == "alias" and aliases and candidate.name in aliases:
            result.append(candidate)
        elif name_match == "regex" and pattern and re.fullmatch(pattern, candidate.name):
            result.append(candidate)
    return result


__all__ = [
    "factory_candidate_origin",
    "factory_candidates_for_class",
    "factory_kind",
    "filter_factory_candidates",
    "filter_static_attribute_factory_candidates",
    "matched_target_parent_class",
    "StaticAttributeFactoryCandidate",
    "static_attribute_factory_candidates_for_class",
]
