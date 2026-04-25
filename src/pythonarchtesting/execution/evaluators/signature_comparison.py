from __future__ import annotations

import ast
from typing import Any

from pythonarchtesting.core.models import EvalContext
from pythonarchtesting.entities import Entity

from .annotation_compatibility import compare_annotation_text


def function_node(entity: Entity) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    node = entity.extras.get("ast_node")
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node
    return None


def param_model(entity: Entity) -> dict[str, Any]:
    synthetic_model = entity.extras.get("synthetic_param_model")
    if isinstance(synthetic_model, dict):
        return synthetic_model

    node = function_node(entity)
    annotations = entity.extras.get("annotations", {}) or {}
    annotation_args = (
        list(annotations.get("args") or []) if isinstance(annotations, dict) else []
    )

    def _param_annotation(param_index: int) -> str | None:
        if 0 <= param_index < len(annotation_args):
            annotation = annotation_args[param_index].get("annotation")
            return str(annotation) if annotation is not None else None
        return None

    if node is None:
        return {
            "params": [],
            "vararg": None,
            "kwarg": None,
            "return_annotation": (
                annotations.get("return") if isinstance(annotations, dict) else None
            ),
            "has_node": False,
        }

    params: list[dict[str, Any]] = []
    args = node.args
    total_pos = len(args.posonlyargs) + len(args.args)
    required_pos = total_pos - len(args.defaults)
    pos_index = 0
    param_index = 0

    for arg in args.posonlyargs:
        params.append(
            {
                "name": arg.arg,
                "kind": "posonly",
                "required": pos_index < required_pos,
                "annotation": _param_annotation(param_index),
            }
        )
        pos_index += 1
        param_index += 1

    for arg in args.args:
        params.append(
            {
                "name": arg.arg,
                "kind": "pos_or_kw",
                "required": pos_index < required_pos,
                "annotation": _param_annotation(param_index),
            }
        )
        pos_index += 1
        param_index += 1

    for index, arg in enumerate(args.kwonlyargs):
        params.append(
            {
                "name": arg.arg,
                "kind": "kwonly",
                "required": args.kw_defaults[index] is None,
                "annotation": _param_annotation(param_index),
            }
        )
        param_index += 1

    return {
        "params": params,
        "vararg": args.vararg.arg if args.vararg is not None else None,
        "kwarg": args.kwarg.arg if args.kwarg is not None else None,
        "return_annotation": (
            annotations.get("return") if isinstance(annotations, dict) else None
        ),
        "has_node": True,
    }


def strip_method_receiver(
    params: list[dict[str, Any]], entity: Entity
) -> list[dict[str, Any]]:
    if entity.kind != "method" or not params:
        return params
    head = params[0]
    if head.get("name") in {"self", "cls"} and head.get("kind") in {
        "posonly",
        "pos_or_kw",
    }:
        return params[1:]
    return params


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


def _decorator_contains_builtin_method_wrapper(node: ast.AST) -> str | None:
    direct_name = _decorator_ref_name(node)
    if direct_name is not None and direct_name.rsplit(".", 1)[-1] in {
        "classmethod",
        "staticmethod",
    }:
        return direct_name.rsplit(".", 1)[-1]

    for child in ast.iter_child_nodes(node):
        nested_name = _decorator_contains_builtin_method_wrapper(child)
        if nested_name is not None:
            return nested_name
    return None


def method_kind(entity: Entity, *, detection_mode: str = "strict") -> str:
    kind = entity.surface_meta.get("method_kind")
    if kind in {"static", "class"}:
        return str(kind)
    if detection_mode != "extended":
        return "instance"

    node = function_node(entity)
    if node is None:
        return "instance"

    detected_kind: str | None = None
    for decorator in node.decorator_list:
        wrapper_name = _decorator_contains_builtin_method_wrapper(decorator)
        if wrapper_name == "classmethod":
            if detected_kind == "static":
                return "instance"
            detected_kind = "class"
        elif wrapper_name == "staticmethod":
            if detected_kind == "class":
                return "instance"
            detected_kind = "static"
    if detected_kind is not None:
        return detected_kind
    return "instance"


def is_async(entity: Entity) -> bool:
    return isinstance(function_node(entity), ast.AsyncFunctionDef)


def method_nonparam_errors(
    source: Entity,
    target: Entity,
    *,
    enforce_method_kind: bool,
) -> list[str]:
    errors: list[str] = []
    if is_async(source) != is_async(target):
        errors.append("async/sync mismatch for required method")
    if enforce_method_kind:
        expected_kind = method_kind(source)
        found_kind = method_kind(target)
        if expected_kind != found_kind:
            errors.append(
                f"method kind mismatch: expected {expected_kind}, found {found_kind}"
            )
    return errors


def return_errors(
    source_model: dict[str, Any],
    target_model: dict[str, Any],
    *,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> list[str]:
    expected_return = source_model.get("return_annotation")
    found_return = target_model.get("return_annotation")
    if expected_return:
        comparison = compare_annotation_text(
            expected=expected_return,
            found=found_return,
            expected_entity=source,
            found_entity=target,
            ctx=ctx,
            variance="covariant",
        )
        if not comparison.compatible:
            return [
                "return annotation mismatch: "
                f"expected {comparison.expected}, found {comparison.found}"
            ]
    return []


def exact_compare(
    expected: list[dict[str, Any]],
    found: list[dict[str, Any]],
    *,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> list[str]:
    errors: list[str] = []
    if len(expected) != len(found):
        errors.append(
            f"parameter count mismatch (expected {len(expected)}, found {len(found)})"
        )
        return errors
    for exp, got in zip(expected, found):
        if exp.get("name") != got.get("name"):
            errors.append(
                f"parameter name mismatch at position '{exp.get('name')}' "
                f"vs '{got.get('name')}'"
            )
        if exp.get("kind") != got.get("kind"):
            errors.append(
                f"parameter kind mismatch for '{exp.get('name')}': "
                f"expected {exp.get('kind')}, found {got.get('kind')}"
            )
        if bool(exp.get("required")) != bool(got.get("required")):
            errors.append(
                f"parameter required/optional mismatch for '{exp.get('name')}'"
            )
        if exp.get("annotation") is not None:
            comparison = compare_annotation_text(
                expected=exp.get("annotation"),
                found=got.get("annotation"),
                expected_entity=source,
                found_entity=target,
                ctx=ctx,
                variance="invariant",
            )
            if not comparison.compatible:
                errors.append(
                    "parameter annotation mismatch for "
                    f"'{exp.get('name')}': expected {comparison.expected}, "
                    f"found {comparison.found}"
                )
    return errors


def compatible_compare(
    expected: list[dict[str, Any]],
    found: list[dict[str, Any]],
    *,
    allow_extra_params: bool,
    allow_param_rename: bool,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> list[str]:
    errors: list[str] = []

    if allow_param_rename:
        expected_non_kw = [param for param in expected if param.get("kind") != "kwonly"]
        found_non_kw = [param for param in found if param.get("kind") != "kwonly"]
        if len(found_non_kw) < len(expected_non_kw):
            errors.append(
                "target has fewer positional-compatible parameters than required"
            )
        else:
            for exp, got in zip(expected_non_kw, found_non_kw):
                if exp.get("kind") != got.get("kind"):
                    errors.append(
                        f"parameter kind mismatch: expected {exp.get('kind')}, "
                        f"found {got.get('kind')}"
                    )
                if exp.get("annotation") is not None:
                    comparison = compare_annotation_text(
                        expected=exp.get("annotation"),
                        found=got.get("annotation"),
                        expected_entity=source,
                        found_entity=target,
                        ctx=ctx,
                        variance="contravariant",
                    )
                    if not comparison.compatible:
                        errors.append(
                            "parameter annotation mismatch: "
                            f"expected {comparison.expected}, found {comparison.found}"
                        )

        expected_kw = [param for param in expected if param.get("kind") == "kwonly"]
        found_kw = [param for param in found if param.get("kind") == "kwonly"]
        if len(found_kw) < len(expected_kw):
            errors.append("target has fewer keyword-only parameters than required")
        else:
            for exp, got in zip(expected_kw, found_kw):
                if exp.get("annotation") is not None:
                    comparison = compare_annotation_text(
                        expected=exp.get("annotation"),
                        found=got.get("annotation"),
                        expected_entity=source,
                        found_entity=target,
                        ctx=ctx,
                        variance="contravariant",
                    )
                    if not comparison.compatible:
                        errors.append(
                            "parameter annotation mismatch: "
                            f"expected {comparison.expected}, found {comparison.found}"
                        )
        return errors

    found_by_name = {str(param.get("name")): param for param in found}
    for exp in expected:
        name = str(exp.get("name"))
        found_param = found_by_name.get(name)
        if found_param is None:
            errors.append(f"missing parameter '{name}'")
            continue
        if exp.get("kind") != found_param.get("kind"):
            errors.append(
                f"parameter kind mismatch for '{name}': "
                f"expected {exp.get('kind')}, found {found_param.get('kind')}"
            )
        if not exp.get("required") and found_param.get("required"):
            errors.append(f"optional parameter became required: '{name}'")
        if exp.get("annotation") is not None:
            comparison = compare_annotation_text(
                expected=exp.get("annotation"),
                found=found_param.get("annotation"),
                expected_entity=source,
                found_entity=target,
                ctx=ctx,
                variance="contravariant",
            )
            if not comparison.compatible:
                errors.append(
                    f"parameter annotation mismatch for '{name}': "
                    f"expected {comparison.expected}, found {comparison.found}"
                )

    if not allow_extra_params:
        expected_names = {str(param.get("name")) for param in expected}
        extra = sorted(
            str(param.get("name"))
            for param in found
            if str(param.get("name")) not in expected_names
        )
        if extra:
            errors.append(f"extra parameters not allowed: {', '.join(extra)}")

    return errors


def evaluate_method_compatibility(
    source: Entity,
    target: Entity,
    *,
    ctx: EvalContext,
    mode: str,
    enforce_method_kind: bool,
    check_return: bool,
) -> dict[str, Any]:
    source_model = param_model(source)
    target_model = param_model(target)

    errors: list[str] = []
    if mode != "any":
        expected_params = strip_method_receiver(source_model.get("params", []), source)
        found_params = strip_method_receiver(target_model.get("params", []), target)

        if mode == "exact":
            errors.extend(
                exact_compare(
                    expected_params,
                    found_params,
                    source=source,
                    target=target,
                    ctx=ctx,
                )
            )
        else:
            errors.extend(
                compatible_compare(
                    expected_params,
                    found_params,
                    allow_extra_params=True,
                    allow_param_rename=False,
                    source=source,
                    target=target,
                    ctx=ctx,
                )
            )
        if bool(source_model.get("vararg")) and not bool(target_model.get("vararg")):
            errors.append("missing *args support required by reference")
        if bool(source_model.get("kwarg")) and not bool(target_model.get("kwarg")):
            errors.append("missing **kwargs support required by reference")

    errors.extend(
        method_nonparam_errors(
            source,
            target,
            enforce_method_kind=enforce_method_kind,
        )
    )

    return {
        "errors": errors,
        "return_errors": (
            return_errors(
                source_model,
                target_model,
                source=source,
                target=target,
                ctx=ctx,
            )
            if check_return
            else []
        ),
        "expected": source_model,
        "found": target_model,
    }


__all__ = [
    "compatible_compare",
    "evaluate_method_compatibility",
    "exact_compare",
    "function_node",
    "is_async",
    "method_kind",
    "method_nonparam_errors",
    "param_model",
    "return_errors",
    "strip_method_receiver",
]
