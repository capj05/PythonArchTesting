from __future__ import annotations

import ast
from typing import Iterable, Sequence

from src.entities import Entity

VALIDATION_SCOPE_ALL = "all"
VALIDATION_SCOPE_LOGICAL_VIEWS = "logical-views"
VALIDATION_SCOPES = (
    VALIDATION_SCOPE_ALL,
    VALIDATION_SCOPE_LOGICAL_VIEWS,
)

_TEMPLATE_SUFFIXES = (
    ".html",
    ".htm",
    ".jinja",
    ".jinja2",
    ".j2",
    ".tpl",
    ".tmpl",
    ".xml",
)


def filter_entities_for_scope(
    entities: Iterable[Entity], scope: str = VALIDATION_SCOPE_ALL
) -> list[Entity]:
    if scope == VALIDATION_SCOPE_ALL:
        return list(entities)
    if scope == VALIDATION_SCOPE_LOGICAL_VIEWS:
        return [entity for entity in entities if is_template_logical_view(entity)]
    raise ValueError(f"Unsupported validation scope: {scope}")


def is_template_logical_view(entity: Entity) -> bool:
    if entity.kind not in {"function", "method"}:
        return False
    ast_node = entity.extras.get("ast_node")
    if not isinstance(ast_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    return _function_uses_template_render(ast_node)


def _function_uses_template_render(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    for subnode in ast.walk(node):
        if not isinstance(subnode, ast.Call):
            continue
        callee = _callee_name(subnode.func)
        if callee in {"render_template", "TemplateResponse"}:
            if _has_template_name(_call_args(subnode)[:1], subnode.keywords):
                return True
        if callee == "render":
            if _has_template_name(_call_args(subnode)[1:2], subnode.keywords):
                return True
    return False


def _call_args(node: ast.Call) -> Sequence[ast.AST]:
    return tuple(node.args)


def _has_template_name(
    positional_args: Sequence[ast.AST], keyword_args: Sequence[ast.keyword]
) -> bool:
    for arg in positional_args:
        value = _string_literal(arg)
        if value and _looks_like_template_name(value):
            return True
    for keyword in keyword_args:
        if keyword.arg not in {"template_name", "name"}:
            continue
        value = _string_literal(keyword.value)
        if value and _looks_like_template_name(value):
            return True
    return False


def _string_literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _looks_like_template_name(value: str) -> bool:
    lowered = value.strip().lower()
    return any(lowered.endswith(suffix) for suffix in _TEMPLATE_SUFFIXES)


def _callee_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


__all__ = [
    "VALIDATION_SCOPE_ALL",
    "VALIDATION_SCOPE_LOGICAL_VIEWS",
    "VALIDATION_SCOPES",
    "filter_entities_for_scope",
    "is_template_logical_view",
]
