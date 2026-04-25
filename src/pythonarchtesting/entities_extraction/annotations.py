from __future__ import annotations

import ast
from typing import Any, Sequence

from pythonarchtesting.entities import AnnotationDeclaration
from pythonarchtesting.protocols.signature_slots import signature_slots
from pythonarchtesting.protocols.type_expr import (
    annotated_details,
    is_annotated_subscript,
    safe_unparse,
)

_MARKER_NAME = "__archtest__"
_POSITIONAL_LIST_ARG_NAMES = {
    "forbid_imports": "forbidden",
}
_POSITIONAL_SINGLE_ARG_NAMES = {
    "does_not_have": "name",
    "exact_type": "base",
    "implements_protocol": "protocol",
    "inherits_directly_from": "base",
    "not_subclass_of": "base",
    "required_attribute": "name",
    "subclass_of": "base",
    "flow": "stage",
    "enforce_flow": "stages",
}
_SUPPORTED_MARKER_NAMES = {
    "does_not_have",
    "enforce_flow",
    "exact_type",
    "forbid_imports",
    "flow",
    "inherits_directly_from",
    "implements_protocol",
    "is_abstract_class",
    "is_concrete_class",
    "is_enum",
    "is_final_class",
    "not_subclass_of",
    "required_attribute",
    "required_constructor",
    "required_entity_signature",
    "required_factory",
    "require_method_set",
    "required_method",
    "subclass_of",
}
_SIGNATURE_SUPPORTED_MARKER_NAMES = {
    "required_entity_signature",
    "implements_protocol",
}


def _literal_value(node: ast.AST) -> tuple[bool, Any]:
    try:
        value = ast.literal_eval(node)
    except Exception:
        return False, None
    return True, value


def _marker_name(node: ast.AST) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return None


def _tuple_metadata_parts(
    node: ast.AST, *, file_text: str
) -> tuple[str | None, dict[str, Any], list[dict[str, Any]]]:
    raw = _raw_segment(file_text, node)
    if not isinstance(node, ast.Tuple) or len(node.elts) != 2:
        return None, {}, [_issue("metadata", node, expr=raw)]

    kind_node, params_node = node.elts
    kind_is_lit, kind_value = _literal_value(kind_node)
    if not kind_is_lit or not isinstance(kind_value, str):
        return (
            None,
            {},
            [_issue("metadata", kind_node, expr=_raw_segment(file_text, kind_node))],
        )

    params_is_lit, params_value = _literal_value(params_node)
    if not params_is_lit or not isinstance(params_value, dict):
        return (
            kind_value,
            {},
            [
                _issue(
                    "metadata", params_node, expr=_raw_segment(file_text, params_node)
                )
            ],
        )

    if not all(isinstance(key, str) for key in params_value):
        return (
            kind_value,
            {},
            [
                _issue(
                    "metadata", params_node, expr=_raw_segment(file_text, params_node)
                )
            ],
        )

    return kind_value, dict(params_value), []


def _metadata_kind_name(node: ast.AST, *, file_text: str) -> str | None:
    name = _marker_name(node)
    if name is not None:
        return name
    tuple_name, _, _ = _tuple_metadata_parts(node, file_text=file_text)
    return tuple_name


def _raw_segment(file_text: str, node: ast.AST) -> str:
    raw = ast.get_source_segment(file_text, node)
    if raw:
        return raw
    return safe_unparse(node)


def _issue(kind: str, node: ast.AST, *, expr: str, **extra: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "expr": expr,
        "lineno": getattr(node, "lineno", 0),
        "col": getattr(node, "col_offset", 0),
        **extra,
    }


def _annotation_details(
    annotation: ast.AST,
    *,
    file_text: str,
    issues: Sequence[dict[str, Any]] = (),
) -> tuple[str, str, list[ast.expr], list[dict[str, Any]]]:
    container = ""
    base_annotation = ""
    metadata_nodes: list[ast.expr] = []
    annotation_issues = list(issues)

    if isinstance(annotation, ast.Subscript):
        container, base_annotation, metadata_nodes = annotated_details(
            annotation,
            unparse=safe_unparse,
        )
        if not is_annotated_subscript(annotation):
            annotation_issues.append(
                _issue(
                    "container",
                    annotation,
                    expr=_raw_segment(file_text, annotation),
                    container=container or safe_unparse(annotation.value),
                )
            )
    else:
        annotation_issues.append(
            _issue(
                "container",
                annotation,
                expr=_raw_segment(file_text, annotation),
                container=safe_unparse(annotation),
            )
        )

    return container, base_annotation, metadata_nodes, annotation_issues


def _metadata_declarations(
    metadata_nodes: Sequence[ast.expr],
    *,
    file_text: str,
    next_order: int,
    container: str,
    base_annotation: str,
    marker_issues: Sequence[dict[str, Any]],
    allowed_marker_names: set[str] | None = None,
    surface: str | None = None,
    subject_kind: str = "",
    subject_index: int = -1,
    subject_name: str = "",
) -> tuple[list[AnnotationDeclaration], int]:
    declarations: list[AnnotationDeclaration] = []

    for metadata_node in metadata_nodes:
        metadata_issues = list(marker_issues)
        name = _metadata_kind_name(metadata_node, file_text=file_text)
        if (
            allowed_marker_names is not None
            and name in _SUPPORTED_MARKER_NAMES
            and name not in allowed_marker_names
        ):
            metadata_issues.append(
                _issue(
                    "surface",
                    metadata_node,
                    expr=_raw_segment(file_text, metadata_node),
                    name=name,
                    allowed=sorted(allowed_marker_names),
                    surface=surface or "",
                )
            )
        declarations.append(
            _parse_metadata_item(
                metadata_node,
                file_text=file_text,
                order=next_order,
                container=container,
                base_annotation=base_annotation,
                marker_issues=metadata_issues,
                surface=surface or "body",
                subject_kind=subject_kind,
                subject_index=subject_index,
                subject_name=subject_name,
            )
        )
        next_order += 1

    return declarations, next_order


def _parse_metadata_item(
    node: ast.AST,
    *,
    file_text: str,
    order: int,
    container: str,
    base_annotation: str,
    marker_issues: Sequence[dict[str, Any]],
    surface: str = "body",
    subject_kind: str = "",
    subject_index: int = -1,
    subject_name: str = "",
) -> AnnotationDeclaration:
    raw = _raw_segment(file_text, node)
    name = _marker_name(node)
    params: dict[str, Any] = {}
    unsupported = list(marker_issues)
    explicit_variable = False

    if isinstance(node, ast.Tuple):
        name, params, tuple_issues = _tuple_metadata_parts(node, file_text=file_text)
        unsupported.extend(tuple_issues)

    if not name:
        unsupported.append(_issue("metadata", node, expr=raw))
        return AnnotationDeclaration(
            kind="unknown",
            params=params,
            unsupported=unsupported,
            raw=raw,
            lineno=getattr(node, "lineno", 0),
            col=getattr(node, "col_offset", 0),
            order=order,
            container=container,
            base_annotation=base_annotation,
            surface=surface,
            subject_kind=subject_kind,
            subject_index=subject_index,
            subject_name=subject_name,
        )

    if name not in _SUPPORTED_MARKER_NAMES:
        unsupported.append(_issue("unknown_metadata", node, expr=raw, name=name))

    if isinstance(node, ast.Call):
        positional_literals: list[Any] = []
        for idx, arg in enumerate(node.args):
            value_repr = safe_unparse(arg)
            is_lit, lit_val = _literal_value(arg)
            if is_lit:
                positional_literals.append(lit_val)
            else:
                unsupported.append(
                    _issue("arg", arg, expr=value_repr, index=idx, name=name)
                )
        positional_list_key = _POSITIONAL_LIST_ARG_NAMES.get(name)
        if positional_list_key and positional_literals:
            params[positional_list_key] = [
                value for value in positional_literals if isinstance(value, str)
            ]
            for idx, value in enumerate(positional_literals):
                if isinstance(value, str):
                    continue
                unsupported.append(
                    _issue(
                        "arg", node.args[idx], expr=repr(value), index=idx, name=name
                    )
                )
        positional_single_key = _POSITIONAL_SINGLE_ARG_NAMES.get(name)
        if positional_single_key and positional_literals:
            params[positional_single_key] = positional_literals[0]
            for idx, value in enumerate(positional_literals):
                if idx == 0 and isinstance(value, str):
                    continue
                if (
                    idx == 0
                    and name == "enforce_flow"
                    and isinstance(value, list)
                    and all(isinstance(item, str) for item in value)
                ):
                    continue
                unsupported.append(
                    _issue(
                        "arg", node.args[idx], expr=repr(value), index=idx, name=name
                    )
                )
        if positional_single_key == "protocol" and node.args:
            params.setdefault("protocol_expr", safe_unparse(node.args[0]))
        for kw in node.keywords:
            key = kw.arg if kw.arg is not None else "**"
            value_repr = safe_unparse(kw.value)
            is_lit, lit_val = _literal_value(kw.value)
            if is_lit and kw.arg is not None:
                params[kw.arg] = lit_val
                if kw.arg == "variable":
                    explicit_variable = True
            else:
                unsupported.append(_issue("kw", kw.value, expr=value_repr, name=key))
            if name == "implements_protocol" and kw.arg == "protocol":
                params["protocol_expr"] = value_repr
        if name == "flow":
            params["variable_explicit"] = explicit_variable

    return AnnotationDeclaration(
        kind=name,
        params=params,
        unsupported=unsupported,
        raw=raw,
        lineno=getattr(node, "lineno", 0),
        col=getattr(node, "col_offset", 0),
        order=order,
        container=container,
        base_annotation=base_annotation,
        surface=surface,
        subject_kind=subject_kind,
        subject_index=subject_index,
        subject_name=subject_name,
    )


def _unsupported_marker_declaration(
    node: ast.AST,
    *,
    order: int,
    file_text: str,
    container: str,
    base_annotation: str,
    issues: Sequence[dict[str, Any]],
    surface: str = "body",
    subject_kind: str = "",
    subject_index: int = -1,
    subject_name: str = "",
) -> AnnotationDeclaration:
    return AnnotationDeclaration(
        kind="unknown",
        params={},
        unsupported=list(issues),
        raw=_raw_segment(file_text, node),
        lineno=getattr(node, "lineno", 0),
        col=getattr(node, "col_offset", 0),
        order=order,
        container=container,
        base_annotation=base_annotation,
        surface=surface,
        subject_kind=subject_kind,
        subject_index=subject_index,
        subject_name=subject_name,
    )


def extract_annotation_declarations(
    body: Sequence[ast.stmt], file_text: str
) -> list[AnnotationDeclaration]:
    declarations: list[AnnotationDeclaration] = []
    next_order = 0

    for stmt in body:
        if not isinstance(stmt, ast.AnnAssign):
            continue
        if not isinstance(stmt.target, ast.Name):
            continue
        if stmt.target.id != _MARKER_NAME or getattr(stmt, "simple", 0) != 1:
            continue

        marker_issues: list[dict[str, Any]] = []
        if stmt.value is not None:
            marker_issues.append(
                _issue(
                    "assigned_value",
                    stmt.value,
                    expr=_raw_segment(file_text, stmt.value),
                )
            )

        annotation = stmt.annotation
        container, base_annotation, metadata_nodes, marker_issues = _annotation_details(
            annotation, file_text=file_text, issues=marker_issues
        )

        if metadata_nodes:
            new_declarations, next_order = _metadata_declarations(
                metadata_nodes,
                file_text=file_text,
                next_order=next_order,
                container=container,
                base_annotation=base_annotation,
                marker_issues=marker_issues,
            )
            declarations.extend(new_declarations)
            continue

        declarations.append(
            _unsupported_marker_declaration(
                annotation,
                order=next_order,
                file_text=file_text,
                container=container,
                base_annotation=base_annotation,
                issues=marker_issues,
            )
        )
        next_order += 1

    return declarations


def _statement_blocks(stmt: ast.stmt) -> list[Sequence[ast.stmt]]:
    blocks: list[Sequence[ast.stmt]] = []
    if isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While)):
        blocks.append(stmt.body)
        if stmt.orelse:
            blocks.append(stmt.orelse)
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        blocks.append(stmt.body)
    elif isinstance(stmt, ast.Try):
        blocks.append(stmt.body)
        for handler in stmt.handlers:
            blocks.append(handler.body)
        if stmt.orelse:
            blocks.append(stmt.orelse)
        if stmt.finalbody:
            blocks.append(stmt.finalbody)
    elif isinstance(stmt, ast.Match):
        for case in stmt.cases:
            blocks.append(case.body)
    return blocks


def _infer_flow_variable(anchor: ast.stmt | None) -> str | None:
    if anchor is None:
        return None
    if isinstance(anchor, ast.Assign) and len(anchor.targets) == 1:
        target = anchor.targets[0]
        if isinstance(target, ast.Name):
            return target.id
    if isinstance(anchor, ast.AnnAssign) and isinstance(anchor.target, ast.Name):
        return anchor.target.id
    if isinstance(anchor, ast.AugAssign) and isinstance(anchor.target, ast.Name):
        return anchor.target.id
    return None


def _flow_anchor_payload(
    anchor: ast.stmt | None, statement_order: int
) -> dict[str, Any]:
    if anchor is None:
        return {
            "anchor_lineno": 0,
            "anchor_col": 0,
            "anchor_kind": "missing",
            "statement_order": statement_order,
        }
    return {
        "anchor_lineno": getattr(anchor, "lineno", 0),
        "anchor_col": getattr(anchor, "col_offset", 0),
        "anchor_kind": type(anchor).__name__,
        "statement_order": statement_order,
    }


def _extract_function_body_declarations_recursive(
    body: Sequence[ast.stmt],
    file_text: str,
    *,
    declarations: list[AnnotationDeclaration],
    next_order: int,
    statement_order: int,
    nested: bool,
) -> tuple[int, int]:
    previous_stmt: ast.stmt | None = None

    for stmt in body:
        if (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == _MARKER_NAME
            and getattr(stmt, "simple", 0) == 1
        ):
            marker_issues: list[dict[str, Any]] = []
            if stmt.value is not None:
                marker_issues.append(
                    _issue(
                        "assigned_value",
                        stmt.value,
                        expr=_raw_segment(file_text, stmt.value),
                    )
                )

            container, base_annotation, metadata_nodes, marker_issues = (
                _annotation_details(
                    stmt.annotation,
                    file_text=file_text,
                    issues=marker_issues,
                )
            )
            if metadata_nodes:
                new_declarations, next_order = _metadata_declarations(
                    metadata_nodes,
                    file_text=file_text,
                    next_order=next_order,
                    container=container,
                    base_annotation=base_annotation,
                    marker_issues=marker_issues,
                    allowed_marker_names={"flow"} if nested else None,
                    surface="body",
                )
                for declaration in new_declarations:
                    if declaration.kind == "flow":
                        params = dict(declaration.params)
                        params.update(
                            _flow_anchor_payload(previous_stmt, statement_order)
                        )
                        params.setdefault(
                            "variable", _infer_flow_variable(previous_stmt)
                        )
                        declaration = AnnotationDeclaration(
                            kind=declaration.kind,
                            params=params,
                            unsupported=list(declaration.unsupported),
                            raw=declaration.raw,
                            lineno=declaration.lineno,
                            col=declaration.col,
                            order=declaration.order,
                            container=declaration.container,
                            base_annotation=declaration.base_annotation,
                            surface="statement",
                            subject_kind=declaration.subject_kind,
                            subject_index=declaration.subject_index,
                            subject_name=declaration.subject_name,
                        )
                    declarations.append(declaration)
                continue

            declarations.append(
                _unsupported_marker_declaration(
                    stmt.annotation,
                    order=next_order,
                    file_text=file_text,
                    container=container,
                    base_annotation=base_annotation,
                    issues=marker_issues,
                )
            )
            next_order += 1
            continue

        statement_order += 1
        blocks = _statement_blocks(stmt)
        if blocks:
            for block in blocks:
                next_order, statement_order = (
                    _extract_function_body_declarations_recursive(
                        block,
                        file_text,
                        declarations=declarations,
                        next_order=next_order,
                        statement_order=statement_order,
                        nested=True,
                    )
                )
        previous_stmt = stmt

    return next_order, statement_order


def extract_function_body_annotation_declarations(
    body: Sequence[ast.stmt],
    file_text: str,
) -> list[AnnotationDeclaration]:
    declarations: list[AnnotationDeclaration] = []
    _extract_function_body_declarations_recursive(
        body,
        file_text,
        declarations=declarations,
        next_order=0,
        statement_order=0,
        nested=False,
    )
    return declarations


def extract_signature_annotation_declarations(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    file_text: str,
) -> list[AnnotationDeclaration]:
    declarations: list[AnnotationDeclaration] = []
    next_order = 0
    for slot in signature_slots(node):
        annotation = getattr(slot.annotation_node, "annotation", slot.annotation_node)
        if not isinstance(annotation, ast.Subscript):
            continue

        container, base_annotation, metadata_nodes, marker_issues = _annotation_details(
            annotation, file_text=file_text
        )
        if not is_annotated_subscript(annotation) or not metadata_nodes:
            continue
        if not any(
            _metadata_kind_name(metadata_node, file_text=file_text)
            in _SUPPORTED_MARKER_NAMES
            for metadata_node in metadata_nodes
        ):
            continue

        new_declarations, next_order = _metadata_declarations(
            metadata_nodes,
            file_text=file_text,
            next_order=next_order,
            container=container,
            base_annotation=base_annotation,
            marker_issues=marker_issues,
            allowed_marker_names=_SIGNATURE_SUPPORTED_MARKER_NAMES,
            surface="signature",
            subject_kind=slot.subject_kind,
            subject_index=slot.subject_index,
            subject_name=slot.subject_name,
        )
        declarations.extend(new_declarations)

    return declarations


__all__ = [
    "extract_annotation_declarations",
    "extract_function_body_annotation_declarations",
    "extract_signature_annotation_declarations",
]
