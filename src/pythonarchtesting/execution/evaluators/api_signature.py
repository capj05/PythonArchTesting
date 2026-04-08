from __future__ import annotations

import ast
from typing import Any, Dict, List

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

from .annotation_compatibility import compare_annotation_text
from .messages import _build_rule_result


def _function_node(entity: Entity) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    node = entity.extras.get("ast_node")
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node
    return None


def _param_model(entity: Entity) -> Dict[str, Any]:
    node = _function_node(entity)
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

    params: List[Dict[str, Any]] = []
    args = node.args
    total_pos = len(args.posonlyargs) + len(args.args)
    required_pos = total_pos - len(args.defaults)
    pos_index = 0
    param_index = 0

    for a in args.posonlyargs:
        params.append(
            {
                "name": a.arg,
                "kind": "posonly",
                "required": pos_index < required_pos,
                "annotation": _param_annotation(param_index),
            }
        )
        pos_index += 1
        param_index += 1

    for a in args.args:
        params.append(
            {
                "name": a.arg,
                "kind": "pos_or_kw",
                "required": pos_index < required_pos,
                "annotation": _param_annotation(param_index),
            }
        )
        pos_index += 1
        param_index += 1

    for idx, a in enumerate(args.kwonlyargs):
        params.append(
            {
                "name": a.arg,
                "kind": "kwonly",
                "required": args.kw_defaults[idx] is None,
                "annotation": _param_annotation(param_index),
            }
        )
        param_index += 1

    return_annotation = None
    if isinstance(annotations, dict):
        return_annotation = annotations.get("return")

    return {
        "params": params,
        "vararg": args.vararg.arg if args.vararg is not None else None,
        "kwarg": args.kwarg.arg if args.kwarg is not None else None,
        "return_annotation": return_annotation,
        "has_node": True,
    }


def _strip_method_receiver(
    params: List[Dict[str, Any]], entity: Entity
) -> List[Dict[str, Any]]:
    if entity.kind != "method" or not params:
        return params
    head = params[0]
    if head.get("name") in {"self", "cls"} and head.get("kind") in {
        "posonly",
        "pos_or_kw",
    }:
        return params[1:]
    return params


def _method_kind(entity: Entity) -> str:
    kind = entity.surface_meta.get("method_kind")
    if kind in {"static", "class"}:
        return str(kind)
    return "instance"


def _is_async(entity: Entity) -> bool:
    node = _function_node(entity)
    return isinstance(node, ast.AsyncFunctionDef)


def _return_errors(
    source_model: Dict[str, Any],
    target_model: Dict[str, Any],
    *,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> List[str]:
    exp_ret = source_model.get("return_annotation")
    got_ret = target_model.get("return_annotation")
    if exp_ret:
        comparison = compare_annotation_text(
            expected=exp_ret,
            found=got_ret,
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


def _exact_compare(
    expected: List[Dict[str, Any]],
    found: List[Dict[str, Any]],
    *,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> List[str]:
    errors: List[str] = []
    if len(expected) != len(found):
        errors.append(f"parameter count mismatch (expected {
            len(expected)}, found {
            len(found)})")
        return errors
    for exp, got in zip(expected, found):
        if exp.get("name") != got.get("name"):
            errors.append(f"parameter name mismatch at position '{
                exp.get('name')}' vs '{
                got.get('name')}'")
        if exp.get("kind") != got.get("kind"):
            errors.append(f"parameter kind mismatch for '{
                exp.get('name')}': expected {
                exp.get('kind')}, found {
                got.get('kind')}")
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


def _compatible_compare(
    expected: List[Dict[str, Any]],
    found: List[Dict[str, Any]],
    *,
    allow_extra_params: bool,
    allow_param_rename: bool,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> List[str]:
    errors: List[str] = []

    if allow_param_rename:
        # Fallback positional compatibility for non-kw-only params.
        expected_non_kw = [p for p in expected if p.get("kind") != "kwonly"]
        found_non_kw = [p for p in found if p.get("kind") != "kwonly"]
        if len(found_non_kw) < len(expected_non_kw):
            errors.append(
                "target has fewer positional-compatible parameters than required"
            )
        else:
            for exp, got in zip(expected_non_kw, found_non_kw):
                if exp.get("kind") != got.get("kind"):
                    errors.append(f"parameter kind mismatch: expected {
                        exp.get('kind')}, found {
                        got.get('kind')}")
                if exp.get("required") and not got.get("required"):
                    # Target being optional is acceptable for compatibility.
                    pass
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
        expected_kw = [p for p in expected if p.get("kind") == "kwonly"]
        found_kw = [p for p in found if p.get("kind") == "kwonly"]
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

    found_by_name = {str(p.get("name")): p for p in found}

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
        expected_names = {str(p.get("name")) for p in expected}
        extra = sorted(
            str(p.get("name"))
            for p in found
            if str(p.get("name")) not in expected_names
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
) -> Dict[str, Any]:
    source_model = _param_model(source)
    target_model = _param_model(target)

    expected_params = _strip_method_receiver(source_model.get("params", []), source)
    found_params = _strip_method_receiver(target_model.get("params", []), target)

    errors: List[str] = []
    if mode == "exact":
        errors.extend(
            _exact_compare(
                expected_params,
                found_params,
                source=source,
                target=target,
                ctx=ctx,
            )
        )
    else:
        errors.extend(
            _compatible_compare(
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
    if _is_async(source) != _is_async(target):
        errors.append("async/sync mismatch for required method")
    if enforce_method_kind:
        expected_kind = _method_kind(source)
        found_kind = _method_kind(target)
        if expected_kind != found_kind:
            errors.append(
                f"method kind mismatch: expected {expected_kind}, found {found_kind}"
            )

    return {
        "errors": errors,
        "return_errors": (
            _return_errors(
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


class ApiSignatureEvaluator:
    """Evaluator for required API signature rules (API001)."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        from pythonarchtesting.core.evidence import (
            get_ast_annotations,
            get_ast_signature,
        )

        source_sig_ev = get_ast_signature(ctx, source.canonical_id, "source")
        target_sig_ev = get_ast_signature(ctx, target.canonical_id, "target")
        source_ann_ev = get_ast_annotations(ctx, source.canonical_id, "source")
        target_ann_ev = get_ast_annotations(ctx, target.canonical_id, "target")

        source_model = _param_model(source)
        target_model = _param_model(target)

        expected_params = _strip_method_receiver(source_model.get("params", []), source)
        found_params = _strip_method_receiver(target_model.get("params", []), target)

        mode = str(rule.params.get("mode", "compatible")).lower()
        allow_extra = bool(rule.params.get("allow_extra_params", True))
        allow_rename = bool(rule.params.get("allow_param_rename", False))
        return_only = bool(rule.params.get("return_only", False))
        check_return = bool(rule.params.get("check_return", False))
        is_required_method_rule = rule.name == "required_method"
        enforce_method_kind = bool(rule.params.get("enforce_method_kind", True))

        errors: List[str] = []
        if not return_only:
            if mode == "exact":
                errors.extend(
                    _exact_compare(
                        expected_params,
                        found_params,
                        source=source,
                        target=target,
                        ctx=ctx,
                    )
                )
            else:
                errors.extend(
                    _compatible_compare(
                        expected_params,
                        found_params,
                        allow_extra_params=allow_extra,
                        allow_param_rename=allow_rename,
                        source=source,
                        target=target,
                        ctx=ctx,
                    )
                )

            if bool(source_model.get("vararg")) and not bool(
                target_model.get("vararg")
            ):
                errors.append("missing *args support required by reference")
            if bool(source_model.get("kwarg")) and not bool(target_model.get("kwarg")):
                errors.append("missing **kwargs support required by reference")

        if is_required_method_rule:
            method_result = evaluate_method_compatibility(
                source,
                target,
                ctx=ctx,
                mode=mode,
                enforce_method_kind=enforce_method_kind,
                check_return=False,
            )
            errors = method_result["errors"]

        if check_return:
            errors.extend(
                _return_errors(
                    source_model,
                    target_model,
                    source=source,
                    target=target,
                    ctx=ctx,
                )
            )

        status: RuleStatus = "OK" if not errors else "FAILED"
        reason = "Signature requirement satisfied." if not errors else "; ".join(errors)
        details = {
            "reason": reason,
            "errors": errors,
            "expected": source_model,
            "found": target_model,
            "mode": mode,
            "return_only": return_only,
            "check_return": check_return,
        }

        return _build_rule_result(
            rule,
            source,
            target,
            match,
            status,
            details,
            (source_sig_ev, target_sig_ev, source_ann_ev, target_ann_ev),
        )


__all__ = ["ApiSignatureEvaluator"]
