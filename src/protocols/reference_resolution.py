from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Sequence

from src.entities import Entity
from src.protocols.entity_lookup import ProtocolEntityLookup
from src.protocols.type_expr import (
    classify_subscript,
    flatten_union_parts,
    matches_supported_container,
)

_SINGLE_CLASS_GENERIC_CONTAINERS = {
    "AbstractSet",
    "Collection",
    "Dict",
    "FrozenSet",
    "Iterable",
    "List",
    "Mapping",
    "MutableMapping",
    "Sequence",
    "Set",
    "Tuple",
    "collections.abc.AbstractSet",
    "collections.abc.Collection",
    "collections.abc.Iterable",
    "collections.abc.Mapping",
    "collections.abc.MutableMapping",
    "collections.abc.Sequence",
    "dict",
    "frozenset",
    "list",
    "set",
    "tuple",
    "typing.AbstractSet",
    "typing.Collection",
    "typing.Dict",
    "typing.FrozenSet",
    "typing.Iterable",
    "typing.List",
    "typing.Mapping",
    "typing.MutableMapping",
    "typing.Sequence",
    "typing.Set",
    "typing.Tuple",
}
_IGNORED_REFERENCE_NAMES = {
    "Any",
    "None",
    "bool",
    "bytes",
    "complex",
    "float",
    "int",
    "object",
    "str",
}
_IGNORED_QUALIFIED_REFERENCES = {
    "builtins.bool",
    "builtins.bytes",
    "builtins.complex",
    "builtins.float",
    "builtins.int",
    "builtins.object",
    "builtins.str",
    "typing.Any",
}


@dataclass(frozen=True)
class ReferenceResolution:
    raw: str
    normalized: str | None
    entity: Entity | None
    reason: str | None = None


def normalize_reference(
    reference: str,
    *,
    module_path: str,
    aliases: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    return _normalize_reference(reference, module_path, aliases or {})


def module_entity_for(
    entity: Entity,
    entities: Sequence[Entity],
    *,
    lookup: ProtocolEntityLookup | None = None,
) -> Entity | None:
    active_lookup = lookup or ProtocolEntityLookup.from_entities(entities)
    return active_lookup.module_entity(entity.module_path)


def import_aliases_for_entity(
    entity: Entity,
    entities: Sequence[Entity],
    *,
    lookup: ProtocolEntityLookup | None = None,
) -> dict[str, str]:
    active_lookup = lookup or ProtocolEntityLookup.from_entities(entities)
    return active_lookup.import_aliases(entity.module_path)


def resolve_reference(
    reference: str,
    *,
    context_entity: Entity,
    entities: Sequence[Entity],
    lookup: ProtocolEntityLookup | None = None,
) -> ReferenceResolution:
    raw = str(reference).strip()
    if not raw:
        return ReferenceResolution(
            raw=raw, normalized=None, entity=None, reason="missing"
        )

    active_lookup = lookup or ProtocolEntityLookup.from_entities(entities)
    aliases = import_aliases_for_entity(context_entity, entities, lookup=active_lookup)
    normalized, reason = normalize_reference(
        raw, module_path=context_entity.module_path, aliases=aliases
    )
    if normalized is None:
        return ReferenceResolution(raw=raw, normalized=None, entity=None, reason=reason)

    matches = active_lookup.class_matches_by_fqn(normalized)
    if len(matches) != 1:
        return ReferenceResolution(
            raw=raw,
            normalized=normalized,
            entity=None,
            reason="ambiguous_or_missing",
        )
    return ReferenceResolution(raw=raw, normalized=normalized, entity=matches[0])


def _normalize_reference(
    reference: str,
    module_path: str,
    aliases: dict[str, str],
) -> tuple[str | None, str | None]:
    try:
        expr = ast.parse(reference, mode="eval").body
    except SyntaxError:
        return None, "unsupported_reference_shape"
    candidates, reason = _extract_reference_candidates(expr, module_path, aliases)
    if candidates is None:
        return None, reason or "unsupported_reference_shape"
    if len(candidates) != 1:
        return None, "ambiguous_or_missing"
    return next(iter(sorted(candidates))), None


def _extract_reference_candidates(
    node: ast.AST,
    module_path: str,
    aliases: dict[str, str],
) -> tuple[set[str] | None, str | None]:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return _extract_reference_candidates_from_text(
                node.value, module_path, aliases
            )
        return None, "unsupported_reference_shape"

    normalized_name = _normalize_name_like_reference(node, module_path, aliases)
    if normalized_name is not None:
        return {normalized_name}, None

    if isinstance(node, ast.Subscript):
        return _extract_subscript_reference_candidates(node, module_path, aliases)

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _extract_union_reference_candidates(
            flatten_union_parts(node), module_path, aliases
        )

    return None, "unsupported_reference_shape"


def _extract_reference_candidates_from_text(
    reference: str,
    module_path: str,
    aliases: dict[str, str],
) -> tuple[set[str] | None, str | None]:
    try:
        expr = ast.parse(reference, mode="eval").body
    except SyntaxError:
        return None, "unsupported_reference_shape"
    return _extract_reference_candidates(expr, module_path, aliases)


def _extract_subscript_reference_candidates(
    node: ast.Subscript,
    module_path: str,
    aliases: dict[str, str],
) -> tuple[set[str] | None, str | None]:
    normalized_container = _normalize_name_like_reference(
        node.value, module_path, aliases
    )
    wrapper = classify_subscript(node, normalized_container=normalized_container)
    parts = list(wrapper.parts)
    if not parts:
        return None, "unsupported_reference_shape"

    if wrapper.kind == "annotated":
        return _extract_reference_candidates(parts[0], module_path, aliases)

    if wrapper.kind == "optional":
        if len(parts) != 1:
            return None, "unsupported_reference_shape"
        return _extract_reference_candidates(parts[0], module_path, aliases)

    if wrapper.kind == "type":
        if len(parts) != 1:
            return None, "unsupported_reference_shape"
        return _extract_reference_candidates(parts[0], module_path, aliases)

    if wrapper.kind == "union":
        return _extract_union_reference_candidates(parts, module_path, aliases)

    if matches_supported_container(
        wrapper.container, normalized_container, _SINGLE_CLASS_GENERIC_CONTAINERS
    ):
        return _collect_generic_reference_candidates(parts, module_path, aliases)

    if normalized_container is not None:
        return {normalized_container}, None

    return None, "unsupported_reference_shape"


def _extract_union_reference_candidates(
    parts: Sequence[ast.AST],
    module_path: str,
    aliases: dict[str, str],
) -> tuple[set[str] | None, str | None]:
    candidates: set[str] = set()
    for part in parts:
        if _is_none_node(part):
            continue
        part_candidates, reason = _extract_reference_candidates(
            part, module_path, aliases
        )
        if part_candidates is None:
            return None, reason or "unsupported_reference_shape"
        candidates.update(part_candidates)

    if not candidates:
        return None, "unsupported_reference_shape"

    return candidates, None


def _collect_generic_reference_candidates(
    parts: Sequence[ast.AST],
    module_path: str,
    aliases: dict[str, str],
) -> tuple[set[str] | None, str | None]:
    candidates: set[str] = set()
    for part in parts:
        if (
            _is_none_node(part)
            or _is_ellipsis_node(part)
            or _is_ignored_leaf_reference(part, module_path, aliases)
        ):
            continue
        part_candidates, reason = _extract_reference_candidates(
            part, module_path, aliases
        )
        if part_candidates is None:
            return None, reason or "unsupported_reference_shape"
        candidates.update(part_candidates)

    if not candidates:
        return None, "unsupported_reference_shape"

    return candidates, None


def _normalize_name_like_reference(
    node: ast.AST,
    module_path: str,
    aliases: dict[str, str],
) -> str | None:
    if isinstance(node, ast.Name):
        alias_target = aliases.get(node.id)
        if alias_target:
            return alias_target
        return f"{module_path}.{node.id}"

    if isinstance(node, ast.Attribute):
        parts = _attribute_parts(node)
        if not parts:
            return None
        root, *rest = parts
        if root in aliases:
            base = aliases[root]
            suffix = ".".join(rest)
            return f"{base}.{suffix}" if suffix else base
        return ".".join(parts)

    return None


def _is_none_node(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return node.value is None
    if isinstance(node, ast.Name):
        return node.id == "None"
    return False


def _is_ellipsis_node(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is Ellipsis


def _is_ignored_leaf_reference(
    node: ast.AST,
    module_path: str,
    aliases: dict[str, str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in _IGNORED_REFERENCE_NAMES
    normalized_name = _normalize_name_like_reference(node, module_path, aliases)
    if normalized_name is None:
        return False
    return normalized_name in _IGNORED_QUALIFIED_REFERENCES


def _attribute_parts(node: ast.Attribute) -> list[str]:
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        parts.reverse()
        return parts
    return []


__all__ = [
    "ReferenceResolution",
    "import_aliases_for_entity",
    "module_entity_for",
    "normalize_reference",
    "resolve_reference",
]
