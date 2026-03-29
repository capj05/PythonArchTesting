from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Callable, Literal

_ANNOTATED_CONTAINERS = {
    "Annotated",
    "typing.Annotated",
    "typing_extensions.Annotated",
}
_OPTIONAL_CONTAINERS = {
    "Optional",
    "typing.Optional",
}
_CLASSVAR_CONTAINERS = {
    "ClassVar",
    "typing.ClassVar",
}
_TYPE_CONTAINERS = {
    "Type",
    "type",
    "typing.Type",
}
_UNION_CONTAINERS = {
    "Union",
    "typing.Union",
}

TypeExprWrapperKind = Literal["annotated", "optional", "type", "union", "other"]


@dataclass(frozen=True)
class TypeExprWrapper:
    kind: TypeExprWrapperKind
    container: str
    parts: tuple[ast.AST, ...]


def safe_unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ast.dump(node, annotate_fields=False, include_attributes=False)


def container_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = container_name(node.value)
        if base:
            return f"{base}.{node.attr}"
        return node.attr
    return None


def subscript_parts(node: ast.AST) -> list[ast.AST]:
    return list(node.elts) if isinstance(node, ast.Tuple) else [node]


def normalize_name_with_aliases(
    node: ast.AST, *, aliases: dict[str, str]
) -> str | None:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = normalize_name_with_aliases(node.value, aliases=aliases)
        if base:
            return f"{base}.{node.attr}"
        return node.attr
    return None


def dotted_name(node: ast.AST) -> str | None:
    return container_name(node)


def flatten_union_parts(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return flatten_union_parts(node.left) + flatten_union_parts(node.right)
    return [node]


def is_annotated_subscript(
    node: ast.Subscript, *, normalized_container: str | None = None
) -> bool:
    raw_container = container_name(node.value)
    return matches_supported_container(
        raw_container, normalized_container, _ANNOTATED_CONTAINERS
    )


def annotated_base_and_metadata(
    node: ast.Subscript,
    *,
    normalized_container: str | None = None,
    unparse: Callable[[ast.AST], str] | None = None,
) -> tuple[str, list[ast.expr]]:
    if not is_annotated_subscript(node, normalized_container=normalized_container):
        return "", []
    parts = subscript_parts(node.slice)
    if not parts:
        return "", []
    render = ast.unparse if unparse is None else unparse
    return render(parts[0]), [part for part in parts[1:] if isinstance(part, ast.expr)]


def annotated_details(
    node: ast.AST,
    *,
    normalized_container: str | None = None,
    unparse: Callable[[ast.AST], str] | None = None,
) -> tuple[str, str, list[ast.expr]]:
    if not isinstance(node, ast.Subscript):
        return "", "", []
    container = container_name(node.value) or ""
    if not is_annotated_subscript(node, normalized_container=normalized_container):
        return container, "", []
    base_annotation, metadata = annotated_base_and_metadata(
        node,
        normalized_container=normalized_container,
        unparse=unparse,
    )
    return container, base_annotation, metadata


def is_classvar_subscript(
    node: ast.Subscript, *, normalized_container: str | None = None
) -> bool:
    raw_container = container_name(node.value)
    return matches_supported_container(
        raw_container, normalized_container, _CLASSVAR_CONTAINERS
    )


def classvar_inner_annotation(
    node: ast.Subscript,
    *,
    normalized_container: str | None = None,
    unparse: Callable[[ast.AST], str] | None = None,
) -> str | None:
    if not is_classvar_subscript(node, normalized_container=normalized_container):
        return None
    parts = subscript_parts(node.slice)
    if not parts:
        return None
    render = ast.unparse if unparse is None else unparse
    return render(parts[0])


def classify_subscript(
    node: ast.Subscript, *, normalized_container: str | None = None
) -> TypeExprWrapper:
    raw_container = container_name(node.value) or safe_unparse(node.value)
    parts = tuple(subscript_parts(node.slice))
    if matches_supported_container(
        raw_container, normalized_container, _ANNOTATED_CONTAINERS
    ):
        kind: TypeExprWrapperKind = "annotated"
    elif matches_supported_container(
        raw_container, normalized_container, _OPTIONAL_CONTAINERS
    ):
        kind = "optional"
    elif matches_supported_container(
        raw_container, normalized_container, _TYPE_CONTAINERS
    ):
        kind = "type"
    elif matches_supported_container(
        raw_container, normalized_container, _UNION_CONTAINERS
    ):
        kind = "union"
    else:
        kind = "other"
    return TypeExprWrapper(kind=kind, container=raw_container, parts=parts)


def unwrap_annotated_annotation_text(
    node: ast.AST | None,
    *,
    normalized_container: str | None = None,
    unparse: Callable[[ast.AST | None], str] | None = None,
) -> str:
    render = safe_unparse if unparse is None else unparse
    if node is None:
        return ""
    if isinstance(node, ast.Subscript):
        base_annotation, _ = annotated_base_and_metadata(
            node,
            normalized_container=normalized_container,
            unparse=lambda part: render(part),
        )
        if base_annotation:
            try:
                return unwrap_annotated_annotation_text(
                    ast.parse(base_annotation, mode="eval").body,
                    normalized_container=normalized_container,
                    unparse=render,
                )
            except SyntaxError:
                return base_annotation
    return render(node)


def matches_supported_container(
    raw_name: str | None,
    normalized_name: str | None,
    supported_names: set[str],
) -> bool:
    return raw_name in supported_names or normalized_name in supported_names


__all__ = [
    "TypeExprWrapper",
    "annotated_base_and_metadata",
    "annotated_details",
    "classvar_inner_annotation",
    "classify_subscript",
    "container_name",
    "dotted_name",
    "flatten_union_parts",
    "is_annotated_subscript",
    "is_classvar_subscript",
    "matches_supported_container",
    "normalize_name_with_aliases",
    "safe_unparse",
    "subscript_parts",
    "unwrap_annotated_annotation_text",
]
