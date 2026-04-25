from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from typing import Literal, Sequence

from pythonarchtesting.entities import Entity, build_canonical_id
from pythonarchtesting.protocols.entity_lookup import ProtocolEntityLookup
from pythonarchtesting.protocols.introspection import declared_class_methods
from pythonarchtesting.protocols.type_expr import (
    classvar_inner_annotation,
    dotted_name,
    safe_unparse,
)

ConstructorKind = Literal["__init__", "__new__"]
ConstructorOrigin = Literal[
    "declared_init",
    "declared_new",
    "generated_dataclass_init",
]

_DATACLASS_DECORATORS = frozenset({"dataclass", "dataclasses.dataclass"})
_FIELD_FACTORIES = frozenset({"field", "dataclasses.field"})
_MISSING_NAMES = frozenset({"MISSING", "dataclasses.MISSING"})


@dataclass(frozen=True)
class ConstructorCandidate:
    entity: Entity
    kind: ConstructorKind
    owner_qualname: str
    inherited: bool
    origin: ConstructorOrigin


def resolve_source_constructor(
    source_class: Entity,
    entities: Sequence[Entity],
    *,
    constructor_kind: str,
) -> ConstructorCandidate | None:
    if constructor_kind == "auto":
        source_init = _declared_or_generated_init(source_class, entities)
        if source_init is not None:
            return source_init
        return _declared_constructor_candidate(source_class, entities, "__new__")

    if constructor_kind == "__init__":
        return _declared_or_generated_init(source_class, entities)

    if constructor_kind == "__new__":
        return _declared_constructor_candidate(source_class, entities, "__new__")

    return None


def constructor_candidates_for_class(
    target_class: Entity,
    entities: Sequence[Entity],
    *,
    allow_inherited: bool,
) -> list[ConstructorCandidate]:
    lookup = ProtocolEntityLookup.from_entities(entities)
    candidates = _collect_constructor_candidates(
        target_class,
        entities,
        lookup=lookup,
        include_bases=allow_inherited,
        visited=set(),
    )
    return sorted(
        candidates.values(),
        key=lambda candidate: (candidate.kind, candidate.owner_qualname),
    )


def resolve_target_constructor(
    target_class: Entity,
    entities: Sequence[Entity],
    *,
    constructor_kind: ConstructorKind,
    allow_inherited: bool,
) -> ConstructorCandidate | None:
    for candidate in constructor_candidates_for_class(
        target_class,
        entities,
        allow_inherited=allow_inherited,
    ):
        if candidate.kind == constructor_kind:
            return candidate
    return None


def constructor_origin_for_entity(
    entity: Entity,
    target_class: Entity,
    entities: Sequence[Entity],
) -> str:
    origin = entity.extras.get("construction_origin")
    if isinstance(origin, str):
        return (
            "inherited"
            if bool(entity.extras.get("construction_inherited"))
            else "declared"
        )

    declared_ids = {
        candidate.canonical_id
        for candidate in declared_class_methods(target_class, list(entities))
    }
    return "declared" if entity.canonical_id in declared_ids else "inherited"


def synthetic_constructor_param_model(
    class_entity: Entity,
) -> dict[str, object] | None:
    node = class_entity.extras.get("ast_node")
    if class_entity.kind != "class" or not isinstance(node, ast.ClassDef):
        return None

    decorator = _dataclass_decorator(node)
    if decorator is None or not _dataclass_init_enabled(decorator):
        return None

    class_kw_only = _decorator_bool_kwarg(decorator, "kw_only", default=False)
    params: list[dict[str, object]] = [
        {
            "name": "self",
            "kind": "pos_or_kw",
            "required": True,
            "annotation": None,
        }
    ]

    for stmt in node.body:
        field_model = _dataclass_field_param(
            stmt,
            class_kw_only=class_kw_only,
        )
        if field_model is None:
            continue
        params.append(field_model)

    return {
        "params": params,
        "vararg": None,
        "kwarg": None,
        "return_annotation": None,
        "has_node": False,
    }


def build_synthetic_constructor_entity(
    class_entity: Entity,
    *,
    name: ConstructorKind,
    origin: ConstructorOrigin,
    inherited: bool,
    param_model: dict[str, object],
) -> Entity:
    signature_key = f"synthetic:{origin}:{name}"
    qualname = f"{class_entity.qualname}.{name}"
    return Entity(
        role=class_entity.role,
        kind="method",
        root_label=class_entity.root_label,
        module_path=class_entity.module_path,
        qualname=qualname,
        name=name,
        filepath_rel=class_entity.filepath_rel,
        lineno=class_entity.lineno,
        signature=None,
        signature_key=signature_key,
        ast_fingerprint="",
        source_hash="",
        doc_hash=None,
        decorators_meta={},
        canonical_id=build_canonical_id(
            class_entity.role,
            class_entity.root_label,
            class_entity.module_path,
            qualname,
            "method",
            signature_key,
        ),
        extras={
            "synthetic_param_model": param_model,
            "construction_origin": origin,
            "construction_inherited": inherited,
            "construction_owner_qualname": class_entity.qualname,
        },
    )


def _collect_constructor_candidates(
    class_entity: Entity,
    entities: Sequence[Entity],
    *,
    lookup: ProtocolEntityLookup,
    include_bases: bool,
    visited: set[str],
) -> dict[ConstructorKind, ConstructorCandidate]:
    if class_entity.kind != "class" or class_entity.canonical_id in visited:
        return {}

    visited.add(class_entity.canonical_id)
    candidates = _local_constructor_candidates(class_entity, entities)

    if not include_bases:
        return {candidate.kind: candidate for candidate in candidates}

    resolved: dict[ConstructorKind, ConstructorCandidate] = {
        candidate.kind: candidate for candidate in candidates
    }
    for base_entity in lookup.resolved_bases(class_entity):
        base_candidates = _collect_constructor_candidates(
            base_entity,
            entities,
            lookup=lookup,
            include_bases=True,
            visited=visited,
        )
        for kind, candidate in base_candidates.items():
            resolved.setdefault(kind, replace(candidate, inherited=True))
    return resolved


def _local_constructor_candidates(
    class_entity: Entity,
    entities: Sequence[Entity],
) -> list[ConstructorCandidate]:
    candidates: list[ConstructorCandidate] = []

    declared_init = _declared_constructor_candidate(class_entity, entities, "__init__")
    if declared_init is not None:
        candidates.append(declared_init)
    else:
        generated_init = _generated_dataclass_init_candidate(class_entity)
        if generated_init is not None:
            candidates.append(generated_init)

    declared_new = _declared_constructor_candidate(class_entity, entities, "__new__")
    if declared_new is not None:
        candidates.append(declared_new)

    return candidates


def _declared_or_generated_init(
    class_entity: Entity,
    entities: Sequence[Entity],
) -> ConstructorCandidate | None:
    declared = _declared_constructor_candidate(class_entity, entities, "__init__")
    if declared is not None:
        return declared
    return _generated_dataclass_init_candidate(class_entity)


def _declared_constructor_candidate(
    class_entity: Entity,
    entities: Sequence[Entity],
    name: ConstructorKind,
) -> ConstructorCandidate | None:
    for method in declared_class_methods(class_entity, list(entities)):
        if method.name != name:
            continue
        return ConstructorCandidate(
            entity=method,
            kind=name,
            owner_qualname=class_entity.qualname,
            inherited=False,
            origin="declared_init" if name == "__init__" else "declared_new",
        )
    return None


def _generated_dataclass_init_candidate(
    class_entity: Entity,
) -> ConstructorCandidate | None:
    param_model = synthetic_constructor_param_model(class_entity)
    if param_model is None:
        return None
    entity = build_synthetic_constructor_entity(
        class_entity,
        name="__init__",
        origin="generated_dataclass_init",
        inherited=False,
        param_model=param_model,
    )
    return ConstructorCandidate(
        entity=entity,
        kind="__init__",
        owner_qualname=class_entity.qualname,
        inherited=False,
        origin="generated_dataclass_init",
    )


def _dataclass_decorator(node: ast.ClassDef) -> ast.AST | None:
    for decorator in node.decorator_list:
        if _decorator_ref_name(decorator) in _DATACLASS_DECORATORS:
            return decorator
    return None


def _dataclass_init_enabled(decorator: ast.AST) -> bool:
    return _decorator_bool_kwarg(decorator, "init", default=True)


def _decorator_bool_kwarg(
    decorator: ast.AST,
    name: str,
    *,
    default: bool,
) -> bool:
    if not isinstance(decorator, ast.Call):
        return default
    value = _call_bool_kwarg(decorator, name)
    return default if value is None else value


def _call_bool_kwarg(call: ast.Call, name: str) -> bool | None:
    for keyword in call.keywords:
        if keyword.arg != name:
            continue
        value = keyword.value
        if isinstance(value, ast.Constant) and isinstance(value.value, bool):
            return value.value
        return None
    return None


def _dataclass_field_param(
    stmt: ast.stmt,
    *,
    class_kw_only: bool,
) -> dict[str, object] | None:
    if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
        return None

    name = stmt.target.id
    if _skip_dataclass_field_name(name):
        return None

    annotation = stmt.annotation
    if _is_classvar_annotation(annotation):
        return None

    field_call = _field_call(stmt.value)
    init_enabled = _field_bool_kwarg(field_call, "init", default=True)
    if not init_enabled and not _is_initvar_annotation(annotation):
        return None
    if not init_enabled and _is_initvar_annotation(annotation):
        return None

    required = _field_is_required(stmt.value)
    kw_only = _field_bool_kwarg(field_call, "kw_only", default=class_kw_only)
    return {
        "name": name,
        "kind": "kwonly" if kw_only else "pos_or_kw",
        "required": required,
        "annotation": safe_unparse(annotation) or None,
    }


def _field_call(value: ast.AST | None) -> ast.Call | None:
    if not isinstance(value, ast.Call):
        return None
    if _decorator_ref_name(value) not in _FIELD_FACTORIES:
        return None
    return value


def _field_is_required(value: ast.AST | None) -> bool:
    call = _field_call(value)
    if call is None:
        return value is None

    default = _field_keyword_value(call, "default")
    if default is not None:
        return _is_missing_marker(default)

    default_factory = _field_keyword_value(call, "default_factory")
    if default_factory is not None:
        return _is_missing_marker(default_factory)

    return True


def _field_keyword_value(call: ast.Call, name: str) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _field_bool_kwarg(call: ast.Call | None, name: str, *, default: bool) -> bool:
    if call is None:
        return default
    value = _call_bool_kwarg(call, name)
    return default if value is None else value


def _is_missing_marker(node: ast.AST) -> bool:
    dotted = dotted_name(node)
    return dotted in _MISSING_NAMES


def _skip_dataclass_field_name(name: str) -> bool:
    if name == "__archtest__":
        return True
    return name.startswith("__") and name.endswith("__")


def _is_classvar_annotation(annotation: ast.AST) -> bool:
    return (
        isinstance(annotation, ast.Subscript)
        and classvar_inner_annotation(annotation) is not None
    )


def _is_initvar_annotation(annotation: ast.AST) -> bool:
    if not isinstance(annotation, ast.Subscript):
        return False
    return dotted_name(annotation.value) in {"InitVar", "dataclasses.InitVar"}


def _decorator_ref_name(node: ast.AST) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    return dotted_name(target)


__all__ = [
    "ConstructorCandidate",
    "ConstructorOrigin",
    "constructor_candidates_for_class",
    "constructor_origin_for_entity",
    "resolve_source_constructor",
    "resolve_target_constructor",
    "synthetic_constructor_param_model",
]
