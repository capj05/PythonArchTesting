from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Literal, Sequence, cast

from src.core.models import EvalContext
from src.entities import Entity
from src.protocols.entity_lookup import ProtocolEntityLookup
from src.protocols.reference_resolution import (
    import_aliases_for_entity,
    resolve_reference,
)
from src.protocols.type_expr import (
    classify_subscript,
    flatten_union_parts,
    normalize_name_with_aliases,
    safe_unparse,
)

_Variance = Literal["invariant", "covariant", "contravariant"]


@dataclass(frozen=True)
class AnnotationComparison:
    compatible: bool
    expected: str | None
    found: str | None


def compare_annotation_text(
    *,
    expected: str | None,
    found: str | None,
    expected_entity: Entity,
    found_entity: Entity,
    ctx: EvalContext,
    variance: _Variance,
) -> AnnotationComparison:
    expected_entities = _entities_for_role(expected_entity, ctx)
    found_entities = _entities_for_role(found_entity, ctx)
    expected_lookup = ProtocolEntityLookup.from_entities(expected_entities)
    found_lookup = ProtocolEntityLookup.from_entities(found_entities)
    expected_norm = normalize_annotation_text(
        expected,
        context_entity=expected_entity,
        entities=expected_entities,
        lookup=expected_lookup,
    )
    found_norm = normalize_annotation_text(
        found,
        context_entity=found_entity,
        entities=found_entities,
        lookup=found_lookup,
    )

    if expected_norm is None:
        return AnnotationComparison(compatible=True, expected=None, found=found_norm)
    if found_norm is None:
        return AnnotationComparison(
            compatible=False, expected=expected_norm, found=None
        )

    expected_resolved = _resolved_annotation_ref(
        expected,
        normalized=expected_norm,
        context_entity=expected_entity,
        entities=expected_entities,
        lookup=expected_lookup,
    )
    found_resolved = _resolved_annotation_ref(
        found,
        normalized=found_norm,
        context_entity=found_entity,
        entities=found_entities,
        lookup=found_lookup,
    )

    if (
        expected_resolved is not None
        and found_resolved is not None
        and _comparable_wrappers(expected_resolved, found_resolved)
    ):
        compatible = _compare_resolved_refs(
            expected_resolved,
            found_resolved,
            found_entities=found_entities,
            found_lookup=found_lookup,
            variance=variance,
        )
        return AnnotationComparison(
            compatible=compatible,
            expected=expected_norm,
            found=found_norm,
        )

    return AnnotationComparison(
        compatible=expected_norm == found_norm,
        expected=expected_norm,
        found=found_norm,
    )


def normalize_annotation_text(
    annotation: str | None,
    *,
    context_entity: Entity,
    entities: Sequence[Entity],
    lookup: ProtocolEntityLookup | None = None,
) -> str | None:
    if annotation is None:
        return None
    text = str(annotation).strip()
    if not text:
        return None
    try:
        node = ast.parse(text, mode="eval").body
    except SyntaxError:
        return text
    active_lookup = lookup or ProtocolEntityLookup.from_entities(entities)
    return _normalize_node(
        node,
        context_entity=context_entity,
        entities=entities,
        lookup=active_lookup,
    )


def _normalize_node(
    node: ast.AST,
    *,
    context_entity: Entity,
    entities: Sequence[Entity],
    lookup: ProtocolEntityLookup,
) -> str:
    if isinstance(node, ast.Subscript):
        wrapper = classify_subscript(node)
        parts = list(wrapper.parts)
        if wrapper.kind == "annotated" and parts:
            return _normalize_node(
                parts[0],
                context_entity=context_entity,
                entities=entities,
                lookup=lookup,
            )
        if wrapper.kind == "optional" and parts:
            inner = _normalize_node(
                parts[0],
                context_entity=context_entity,
                entities=entities,
                lookup=lookup,
            )
            return _normalized_union_parts([inner, "None"])
        if wrapper.kind == "type" and parts:
            inner = _normalize_node(
                parts[0],
                context_entity=context_entity,
                entities=entities,
                lookup=lookup,
            )
            return f"type[{inner}]"
        if wrapper.kind == "union":
            return _normalized_union_parts(
                [
                    _normalize_node(
                        part,
                        context_entity=context_entity,
                        entities=entities,
                        lookup=lookup,
                    )
                    for part in parts
                ]
            )
        normalized_container = _normalize_name_like(
            node.value,
            context_entity=context_entity,
            entities=entities,
            lookup=lookup,
        )
        normalized_parts = [
            _normalize_node(
                part,
                context_entity=context_entity,
                entities=entities,
                lookup=lookup,
            )
            for part in parts
        ]
        return f"{normalized_container}[{', '.join(normalized_parts)}]"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _normalized_union_parts(
            [
                _normalize_node(
                    part,
                    context_entity=context_entity,
                    entities=entities,
                    lookup=lookup,
                )
                for part in flatten_union_parts(node)
            ]
        )
    if isinstance(node, ast.Constant) and node.value is None:
        return "None"
    return _normalize_name_like(
        node,
        context_entity=context_entity,
        entities=entities,
        lookup=lookup,
    )


def _normalized_union_parts(parts: Sequence[str]) -> str:
    flattened = sorted(dict.fromkeys(parts))
    return " | ".join(flattened)


def _normalize_name_like(
    node: ast.AST,
    *,
    context_entity: Entity,
    entities: Sequence[Entity],
    lookup: ProtocolEntityLookup,
) -> str:
    text = ast.unparse(node)
    resolution = resolve_reference(
        text,
        context_entity=context_entity,
        entities=entities,
        lookup=lookup,
    )
    if resolution.entity is not None and resolution.normalized:
        return resolution.normalized
    return _normalize_with_aliases(
        node,
        aliases=import_aliases_for_entity(context_entity, entities, lookup=lookup),
    )


def _normalize_with_aliases(node: ast.AST, *, aliases: dict[str, str]) -> str:
    normalized = normalize_name_with_aliases(node, aliases=aliases)
    if normalized is not None:
        return normalized
    return safe_unparse(node)


@dataclass(frozen=True)
class _ResolvedAnnotationRef:
    kind: str
    ref: str
    entity: Entity | None
    inner: _ResolvedAnnotationRef | None = None
    parts: tuple[_ResolvedAnnotationRef, ...] = ()


def _resolved_annotation_ref(
    raw: str | None,
    *,
    normalized: str,
    context_entity: Entity,
    entities: Sequence[Entity],
    lookup: ProtocolEntityLookup,
) -> _ResolvedAnnotationRef | None:
    expr = raw if raw is not None else normalized
    try:
        node = ast.parse(expr, mode="eval").body
    except SyntaxError:
        try:
            node = ast.parse(normalized, mode="eval").body
        except SyntaxError:
            return None
    return _resolve_node(
        node,
        context_entity=context_entity,
        entities=entities,
        lookup=lookup,
    )


def _resolve_node(
    node: ast.AST,
    *,
    context_entity: Entity,
    entities: Sequence[Entity],
    lookup: ProtocolEntityLookup,
) -> _ResolvedAnnotationRef | None:
    if isinstance(node, ast.Subscript):
        wrapper = classify_subscript(node)
        parts = list(wrapper.parts)
        if wrapper.kind == "annotated" and parts:
            return _resolve_node(
                parts[0],
                context_entity=context_entity,
                entities=entities,
                lookup=lookup,
            )
        if wrapper.kind == "optional" and parts:
            return _resolve_union_parts(
                [parts[0], ast.Constant(value=None)],
                context_entity=context_entity,
                entities=entities,
                lookup=lookup,
            )
        if wrapper.kind == "type" and parts:
            inner = _resolve_node(
                parts[0],
                context_entity=context_entity,
                entities=entities,
                lookup=lookup,
            )
            if inner is None:
                return None
            return _ResolvedAnnotationRef(
                kind="type",
                ref=f"type[{inner.ref}]",
                entity=None,
                inner=inner,
            )
        if wrapper.kind == "union":
            return _resolve_union_parts(
                parts,
                context_entity=context_entity,
                entities=entities,
                lookup=lookup,
            )
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _resolve_union_parts(
            flatten_union_parts(node),
            context_entity=context_entity,
            entities=entities,
            lookup=lookup,
        )
    if isinstance(node, ast.Constant) and node.value is None:
        return _ResolvedAnnotationRef(kind="none", ref="None", entity=None)
    text = ast.unparse(node)
    resolution = resolve_reference(
        text,
        context_entity=context_entity,
        entities=entities,
        lookup=lookup,
    )
    if resolution.entity is None or resolution.normalized is None:
        return None
    return _ResolvedAnnotationRef(
        kind="entity",
        ref=resolution.normalized,
        entity=resolution.entity,
    )


def _resolve_union_parts(
    parts: Sequence[ast.AST],
    *,
    context_entity: Entity,
    entities: Sequence[Entity],
    lookup: ProtocolEntityLookup,
) -> _ResolvedAnnotationRef | None:
    resolved_parts = [
        _resolve_node(
            part,
            context_entity=context_entity,
            entities=entities,
            lookup=lookup,
        )
        for part in parts
    ]
    if any(part is None for part in resolved_parts):
        return None
    concrete_parts = cast(list[_ResolvedAnnotationRef], resolved_parts)
    refs = sorted(dict.fromkeys(part.ref for part in concrete_parts))
    return _ResolvedAnnotationRef(
        kind="union",
        ref=" | ".join(refs),
        entity=None,
        parts=tuple(sorted(concrete_parts, key=_shape_key)),
    )


def _comparable_wrappers(
    expected: _ResolvedAnnotationRef,
    found: _ResolvedAnnotationRef,
) -> bool:
    if expected.kind != found.kind:
        return False
    if expected.kind == "entity":
        return expected.entity is not None and found.entity is not None
    if expected.kind == "type":
        return expected.inner is not None and found.inner is not None
    if expected.kind in {"union", "none"}:
        return True
    return False


def _compare_resolved_refs(
    expected: _ResolvedAnnotationRef,
    found: _ResolvedAnnotationRef,
    *,
    found_entities: Sequence[Entity],
    found_lookup: ProtocolEntityLookup,
    variance: _Variance,
) -> bool:
    if expected.kind == "entity":
        assert expected.entity is not None
        assert found.entity is not None
        if variance == "covariant":
            return _is_same_or_subtype(
                found.entity,
                expected.entity.name,
                entities=found_entities,
                lookup=found_lookup,
            )
        if variance == "contravariant":
            target_expected = _find_class_by_name(
                found_entities,
                expected.entity.name,
                lookup=found_lookup,
            )
            if target_expected is None:
                return expected.entity.name == found.entity.name
            return _is_same_or_subtype(
                target_expected,
                found.entity.name,
                entities=found_entities,
                lookup=found_lookup,
            )
        return expected.entity.name == found.entity.name
    if expected.kind == "type":
        assert expected.inner is not None
        assert found.inner is not None
        return _compare_resolved_refs(
            expected.inner,
            found.inner,
            found_entities=found_entities,
            found_lookup=found_lookup,
            variance=variance,
        )
    if expected.kind == "union":
        return [_shape_key(part) for part in expected.parts] == [
            _shape_key(part) for part in found.parts
        ]
    return expected.ref == found.ref


def _is_same_or_subtype(
    candidate: Entity,
    expected_name: str,
    *,
    entities: Sequence[Entity],
    lookup: ProtocolEntityLookup,
) -> bool:
    if candidate.name == expected_name:
        return True
    return _inherits_from(
        candidate,
        expected_name,
        entities=entities,
        lookup=lookup,
        seen=set(),
    )


def _inherits_from(
    entity: Entity,
    expected_name: str,
    *,
    entities: Sequence[Entity],
    lookup: ProtocolEntityLookup,
    seen: set[str],
) -> bool:
    if entity.canonical_id in seen:
        return False
    seen.add(entity.canonical_id)
    _ = entities
    for base_entity in lookup.resolved_bases(entity):
        if base_entity.name == expected_name:
            return True
        if _inherits_from(
            base_entity,
            expected_name,
            entities=entities,
            lookup=lookup,
            seen=seen,
        ):
            return True
    return False


def _find_class_by_name(
    entities: Sequence[Entity],
    name: str,
    *,
    lookup: ProtocolEntityLookup,
) -> Entity | None:
    _ = entities
    return lookup.class_by_name(name)


def _shape_key(ref: _ResolvedAnnotationRef) -> str:
    if ref.kind == "entity" and ref.entity is not None:
        return ref.entity.name
    if ref.kind == "type" and ref.inner is not None:
        return f"type[{_shape_key(ref.inner)}]"
    if ref.kind == "union":
        return " | ".join(_shape_key(part) for part in ref.parts)
    return ref.ref


def _entities_for_role(entity: Entity, ctx: EvalContext) -> Sequence[Entity]:
    entities = (
        ctx.source_index.all_sorted
        if entity.role == "source"
        else ctx.target_index.all_sorted
    )
    return cast(Sequence[Entity], entities)


__all__ = [
    "AnnotationComparison",
    "compare_annotation_text",
    "normalize_annotation_text",
]
