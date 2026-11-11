from __future__ import annotations

import ast
from typing import Any, Literal

from pythonarchtesting.core.models import EvalContext
from pythonarchtesting.entities import Entity

from .annotation_compatibility import compare_annotation_text

_FEWER_POSITIONAL = "target has fewer positional-compatible parameters than required"
_FEWER_KWONLY = "target has fewer keyword-only parameters than required"


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


def _annotation_error(
    subject: str,
    expected: str | None,
    found: str | None,
    *,
    variance: Literal["invariant", "covariant", "contravariant"],
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> str | None:
    """Compare one expected annotation with the found one and describe a mismatch.

    The ``subject`` opens the message (for example ``"return annotation
    mismatch"``), so every caller keeps its own wording while the comparison
    and the ``expected …, found …`` tail are written once. An expected
    annotation of ``None`` places no requirement and yields no error.
    """
    if expected is None:
        return None
    comparison = compare_annotation_text(
        expected=expected,
        found=found,
        expected_entity=source,
        found_entity=target,
        ctx=ctx,
        variance=variance,
    )
    if comparison.compatible:
        return None
    return f"{subject}: expected {comparison.expected}, found {comparison.found}"


def return_errors(
    source_model: dict[str, Any],
    target_model: dict[str, Any],
    *,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> list[str]:
    expected_return = source_model.get("return_annotation")
    if not expected_return:
        return []
    error = _annotation_error(
        "return annotation mismatch",
        expected_return,
        target_model.get("return_annotation"),
        variance="covariant",
        source=source,
        target=target,
        ctx=ctx,
    )
    return [error] if error else []


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
        error = _annotation_error(
            f"parameter annotation mismatch for '{exp.get('name')}'",
            exp.get("annotation"),
            got.get("annotation"),
            variance="invariant",
            source=source,
            target=target,
            ctx=ctx,
        )
        if error:
            errors.append(error)
    return errors


def _compare_positional(
    expected: list[dict[str, Any]],
    found: list[dict[str, Any]],
    *,
    fewer_message: str,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> list[str]:
    """Pair parameters by position and report kind and annotation mismatches.

    Names are not compared, which is what lets a target rename a parameter.
    When the target has fewer parameters, only ``fewer_message`` is reported
    and no pair is checked. Extra target parameters beyond the expected ones
    are not inspected. The messages carry no parameter name, because the
    names of the pair may differ.
    """
    if len(found) < len(expected):
        return [fewer_message]
    errors: list[str] = []
    for exp, got in zip(expected, found):
        if exp.get("kind") != got.get("kind"):
            errors.append(
                f"parameter kind mismatch: expected {exp.get('kind')}, "
                f"found {got.get('kind')}"
            )
        error = _annotation_error(
            "parameter annotation mismatch",
            exp.get("annotation"),
            got.get("annotation"),
            variance="contravariant",
            source=source,
            target=target,
            ctx=ctx,
        )
        if error:
            errors.append(error)
    return errors


def _split_kwonly(
    params: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split parameters into positional-compatible and keyword-only ones.

    Both parts keep the declaration order. A parameter without a ``kind`` counts
    as positional-compatible.
    """
    non_kw: list[dict[str, Any]] = []
    kw: list[dict[str, Any]] = []
    for param in params:
        if param.get("kind") == "kwonly":
            kw.append(param)
        else:
            non_kw.append(param)
    return non_kw, kw


def _compare_by_position(
    expected: list[dict[str, Any]],
    found: list[dict[str, Any]],
    *,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> list[str]:
    """Compare positional and keyword-only parameters separately, by position.

    Positional-compatible parameters are compared first, then the keyword-only
    ones, each group in its declaration order. The kind check inside
    ``_compare_positional`` cannot fire for the keyword-only group, since both
    sides of it hold only ``kwonly`` parameters.
    """
    expected_non_kw, expected_kw = _split_kwonly(expected)
    found_non_kw, found_kw = _split_kwonly(found)
    return _compare_positional(
        expected_non_kw,
        found_non_kw,
        fewer_message=_FEWER_POSITIONAL,
        source=source,
        target=target,
        ctx=ctx,
    ) + _compare_positional(
        expected_kw,
        found_kw,
        fewer_message=_FEWER_KWONLY,
        source=source,
        target=target,
        ctx=ctx,
    )


def _compare_by_name(
    expected: list[dict[str, Any]],
    found: list[dict[str, Any]],
    *,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> list[str]:
    """Pair every expected parameter with the target parameter of its name.

    For each pair the kind, a change from optional to required, and the
    annotation are checked, in that order. A missing parameter is reported
    once and its other checks are skipped. When the target repeats a name,
    the last parameter of that name is used.
    """
    found_by_name = {str(param.get("name")): param for param in found}
    errors: list[str] = []
    for exp in expected:
        name = str(exp.get("name"))
        got = found_by_name.get(name)
        if got is None:
            errors.append(f"missing parameter '{name}'")
            continue
        if exp.get("kind") != got.get("kind"):
            errors.append(
                f"parameter kind mismatch for '{name}': "
                f"expected {exp.get('kind')}, found {got.get('kind')}"
            )
        if not exp.get("required") and got.get("required"):
            errors.append(f"optional parameter became required: '{name}'")
        error = _annotation_error(
            f"parameter annotation mismatch for '{name}'",
            exp.get("annotation"),
            got.get("annotation"),
            variance="contravariant",
            source=source,
            target=target,
            ctx=ctx,
        )
        if error:
            errors.append(error)
    return errors


def _extra_param_errors(
    expected: list[dict[str, Any]],
    found: list[dict[str, Any]],
    *,
    allow_extra_params: bool,
) -> list[str]:
    """Report target parameters whose names the reference does not have.

    Without ``allow_extra_params`` every extra parameter is an error. With it,
    only the required ones are, since callers of the reference's signature do
    not pass them.
    """
    expected_names = {str(param.get("name")) for param in expected}
    extra = [param for param in found if str(param.get("name")) not in expected_names]
    if not allow_extra_params:
        if not extra:
            return []
        names = sorted(str(param.get("name")) for param in extra)
        return [f"extra parameters not allowed: {', '.join(names)}"]
    required = sorted(
        str(param.get("name")) for param in extra if param.get("required")
    )
    if not required:
        return []
    return [
        f"extra required parameter(s) {', '.join(required)}: "
        "callers of the reference's signature do not pass them"
    ]


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
    """Check that a target's parameters can stand in for the expected ones.

    With ``allow_param_rename`` the parameters are paired by position, so
    names are free to differ; otherwise they are paired by name and extra
    target parameters are checked against ``allow_extra_params``. The
    by-position comparison does not check extra parameters at all, so
    ``allow_extra_params`` has no effect there; this is the existing
    behaviour, kept as it is.
    """
    if allow_param_rename:
        return _compare_by_position(
            expected, found, source=source, target=target, ctx=ctx
        )
    return _compare_by_name(
        expected, found, source=source, target=target, ctx=ctx
    ) + _extra_param_errors(expected, found, allow_extra_params=allow_extra_params)


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
