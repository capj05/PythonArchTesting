from __future__ import annotations

import ast
from typing import Any, Dict, List

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

from .annotation_compatibility import compare_annotation_text
from .factory_resolution import (
    factory_candidates_for_class,
    factory_kind,
    filter_factory_candidates,
)
from .member_name_resolution import (
    filter_methods_by_name_match,
    matched_target_parent_class,
)
from .member_name_resolution import member_origin as resolved_member_origin
from .member_name_resolution import (
    target_methods_for_class,
    target_parent_class,
)
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


def _method_nonparam_errors(
    source: Entity,
    target: Entity,
    *,
    enforce_method_kind: bool,
) -> List[str]:
    errors: List[str] = []
    if _is_async(source) != _is_async(target):
        errors.append("async/sync mismatch for required method")
    if enforce_method_kind:
        expected_kind = _method_kind(source)
        found_kind = _method_kind(target)
        if expected_kind != found_kind:
            errors.append(
                f"method kind mismatch: expected {expected_kind}, found {found_kind}"
            )
    return errors


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
        errors.append(
            f"parameter count mismatch (expected {len(expected)}, "
            f"found {len(found)})"
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
                    errors.append(
                        f"parameter kind mismatch: expected {exp.get('kind')}, "
                        f"found {got.get('kind')}"
                    )
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

    errors: List[str] = []
    if mode != "any":
        expected_params = _strip_method_receiver(source_model.get("params", []), source)
        found_params = _strip_method_receiver(target_model.get("params", []), target)

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

    errors.extend(
        _method_nonparam_errors(
            source,
            target,
            enforce_method_kind=enforce_method_kind,
        )
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


def _resolve_required_method_class(
    source: Entity,
    target: Entity,
    *,
    ctx: EvalContext,
) -> Entity | None:
    if target.kind == "class":
        return target
    if target.kind == "method":
        target_class = target_parent_class(target, ctx)
        if target_class is not None:
            return target_class
    return matched_target_parent_class(source, ctx)


def _evaluate_required_method_against_candidate(
    rule: Rule,
    source: Entity,
    candidate: Entity,
    match: MatchResult,
    evidence: tuple[Any, ...],
    *,
    ctx: EvalContext,
    mode: str,
    check_return: bool,
    allow_missing: bool,
    declared_only: bool,
    enforce_method_kind: bool,
    member_resolution: str,
    member_origin: str,
    details_extra: dict[str, Any] | None = None,
) -> RuleResult:
    method_result = evaluate_method_compatibility(
        source,
        candidate,
        ctx=ctx,
        mode=mode,
        enforce_method_kind=enforce_method_kind,
        check_return=False,
    )
    errors = method_result["errors"]
    status: RuleStatus = "OK" if not errors else "FAILED"
    reason = "Required method satisfied." if not errors else "; ".join(errors)
    details = {
        "reason": reason,
        "errors": errors,
        "expected": method_result["expected"],
        "found": method_result["found"],
        "mode": mode,
        "params_ignored": mode == "any",
        "return_only": False,
        "check_return": check_return,
        "allow_missing": allow_missing,
        "declared_only": declared_only,
        "member_resolution": member_resolution,
        "member_origin": member_origin,
    }
    if details_extra:
        details.update(details_extra)
    return _build_rule_result(
        rule,
        source,
        candidate,
        match,
        status,
        details,
        evidence,
    )


def _skip_optional_required_method(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    evidence: tuple[Any, ...],
    *,
    mode: str,
    declared_only: bool,
    member_resolution: str,
    member_origin: str,
    details_extra: dict[str, Any] | None = None,
) -> RuleResult:
    details = {
        "skipped": True,
        "reason": "optional_member_absent",
        "errors": [],
        "mode": mode,
        "params_ignored": mode == "any",
        "check_return": False,
        "allow_missing": True,
        "declared_only": declared_only,
        "member_resolution": member_resolution,
        "member_origin": member_origin,
    }
    if details_extra:
        details.update(details_extra)
    return _build_rule_result(
        rule,
        source,
        target,
        match,
        "SKIPPED",
        details,
        evidence,
    )


def _flexible_match_reason(
    *,
    name_match: str,
    source_name: str,
    aliases: list[str] | None,
    pattern: str | None,
) -> str:
    if name_match == "alias":
        accepted = ", ".join([source_name, *(aliases or [])])
        return f"no compatible candidate found for aliases: {accepted}"
    if name_match == "regex":
        return f"no compatible candidate found for pattern '{pattern}'"
    return "no compatible candidate found with unconstrained name matching"


def _evaluate_required_factory_rule(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    *,
    ctx: EvalContext,
    mode: str,
    rule_evidence: tuple[Any, ...],
    aliases: list[str] | None,
    pattern: str | None,
) -> RuleResult:
    satisfy_with = [
        str(value)
        for value in rule.params.get(
            "satisfy_with",
            ["constructor", "classmethod", "staticmethod"],
        )
    ]
    allow_inherited = bool(rule.params.get("allow_inherited", True))
    name_match = str(rule.params.get("name_match", "any")).lower()
    target_class: Entity | None

    if target.kind == "class":
        target_class = target
    elif target.kind == "method":
        target_class = target_parent_class(target, ctx)
    else:
        target_class = matched_target_parent_class(source, ctx)

    if target_class is None:
        details = {
            "reason": "no_factory_candidate_found",
            "factory_rule": {
                "satisfy_with": satisfy_with,
                "allow_inherited": allow_inherited,
                "name_match": name_match,
                "aliases": aliases,
                "pattern": pattern,
            },
            "candidate_factories": [],
            "selected_candidate": None,
        }
        return _build_rule_result(
            rule,
            source,
            target,
            match,
            "FAILED",
            details,
            rule_evidence,
        )

    candidates = factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=allow_inherited,
    )
    filtered_candidates = filter_factory_candidates(
        candidates,
        satisfy_with=satisfy_with,
        name_match=name_match,
        source_name=source.name,
        aliases=aliases,
        pattern=pattern,
    )

    candidate_details: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_kind = factory_kind(candidate)
        candidate_accepted = candidate in filtered_candidates
        candidate_details.append(
            {
                "entity_id": candidate.canonical_id,
                "qualname": candidate.qualname,
                "name": candidate.name,
                "factory_kind": candidate_kind,
                "method_kind": _method_kind(candidate),
                "inherited": resolved_member_origin(candidate, target_class, ctx)
                != "declared",
                "accepted": candidate_accepted,
                "errors": (
                    []
                    if candidate_accepted
                    else ["filtered out by satisfy_with or name_match"]
                ),
            }
        )

    if not filtered_candidates:
        details = {
            "reason": "no_factory_candidate_found",
            "factory_rule": {
                "satisfy_with": satisfy_with,
                "allow_inherited": allow_inherited,
                "name_match": name_match,
                "aliases": aliases,
                "pattern": pattern,
            },
            "candidate_factories": candidate_details,
            "selected_candidate": None,
        }
        return _build_rule_result(
            rule,
            source,
            target_class,
            match,
            "FAILED",
            details,
            rule_evidence,
        )

    compatible_candidates: list[tuple[Entity, list[str]]] = []
    for candidate in filtered_candidates:
        candidate_result = evaluate_method_compatibility(
            source,
            candidate,
            ctx=ctx,
            mode=mode,
            enforce_method_kind=False,
            check_return=False,
        )
        errors = list(candidate_result["errors"])
        for item in candidate_details:
            if item["entity_id"] == candidate.canonical_id:
                item["accepted"] = not errors
                item["errors"] = errors
                break
        if not errors:
            compatible_candidates.append((candidate, errors))

    if not compatible_candidates:
        details = {
            "reason": "no_compatible_factory_candidate",
            "factory_rule": {
                "satisfy_with": satisfy_with,
                "allow_inherited": allow_inherited,
                "name_match": name_match,
                "aliases": aliases,
                "pattern": pattern,
            },
            "candidate_factories": candidate_details,
            "selected_candidate": None,
        }
        return _build_rule_result(
            rule,
            source,
            target_class,
            match,
            "FAILED",
            details,
            rule_evidence,
        )

    if len(compatible_candidates) > 1:
        details = {
            "reason": "multiple_compatible_factory_candidates",
            "factory_rule": {
                "satisfy_with": satisfy_with,
                "allow_inherited": allow_inherited,
                "name_match": name_match,
                "aliases": aliases,
                "pattern": pattern,
            },
            "candidate_factories": candidate_details,
            "selected_candidate": None,
        }
        return _build_rule_result(
            rule,
            source,
            target_class,
            match,
            "FAILED",
            details,
            rule_evidence,
        )

    selected_candidate, _ = compatible_candidates[0]
    details = {
        "reason": "Factory requirement satisfied.",
        "factory_rule": {
            "satisfy_with": satisfy_with,
            "allow_inherited": allow_inherited,
            "name_match": name_match,
            "aliases": aliases,
            "pattern": pattern,
        },
        "candidate_factories": candidate_details,
        "selected_candidate": {
            "entity_id": selected_candidate.canonical_id,
            "qualname": selected_candidate.qualname,
            "name": selected_candidate.name,
        },
    }
    return _build_rule_result(
        rule,
        source,
        selected_candidate,
        match,
        "OK",
        details,
        rule_evidence,
    )


def _evaluate_required_constructor_rule(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    *,
    ctx: EvalContext,
    mode: str,
    rule_evidence: tuple[Any, ...],
) -> RuleResult:
    constructor_kind = str(rule.params.get("constructor_kind", "auto")).lower()
    resolved_kind = str(
        rule.params.get("resolved_constructor_kind", constructor_kind)
    ).lower()
    allow_inherited = bool(rule.params.get("allow_inherited", True))
    expected_source_id = rule.params.get("expected_source_constructor_id")

    constructor_details = {
        "kind": constructor_kind,
        "resolved_kind": resolved_kind,
        "allow_inherited": allow_inherited,
    }

    target_class: Entity | None = target if target.kind == "class" else None
    if target_class is None:
        details = {
            "reason": "required_constructor requires a matched target class",
            "errors": ["required_constructor requires a matched target class"],
            "mode": mode,
            "check_return": False,
            "constructor": constructor_details,
            "resolved_target_constructor": None,
            "member_origin": "missing",
        }
        return _build_rule_result(
            rule,
            source,
            target,
            match,
            "FAILED",
            details,
            rule_evidence,
        )

    source_ctor = (
        ctx.source_by_id.get(str(expected_source_id))
        if expected_source_id is not None
        else None
    )
    if not isinstance(source_ctor, Entity) or source_ctor.kind != "method":
        details = {
            "reason": (
                "compiler did not resolve a source constructor for "
                "required_constructor"
            ),
            "errors": [
                "compiler did not resolve a source constructor for "
                "required_constructor"
            ],
            "mode": mode,
            "check_return": False,
            "constructor": constructor_details,
            "resolved_target_constructor": None,
            "member_origin": "missing",
        }
        return _build_rule_result(
            rule,
            source,
            target_class,
            match,
            "FAILED",
            details,
            rule_evidence,
        )

    declared_targets = {
        method.name: method
        for method in target_methods_for_class(
            target_class, ctx, include_inherited=False
        )
    }
    all_targets = {
        method.name: method
        for method in target_methods_for_class(
            target_class, ctx, include_inherited=True
        )
    }

    target_ctor: Entity | None = declared_targets.get(resolved_kind)
    member_origin = "declared" if target_ctor is not None else "missing"

    if target_ctor is None and allow_inherited:
        target_ctor = all_targets.get(resolved_kind)
        if target_ctor is not None:
            member_origin = "inherited"

    if target_ctor is None:
        inherited_only = (
            resolved_kind in all_targets and resolved_kind not in declared_targets
        )
        if inherited_only and not allow_inherited:
            reason = (
                "constructor is inherited but not declared directly on " "target class"
            )
            member_origin = "inherited"
            failure_reason = "constructor_inherited_not_allowed"
        else:
            reason = f"missing required constructor '{resolved_kind}'"
            failure_reason = "missing_constructor"
        details = {
            "reason": reason,
            "errors": [reason],
            "mode": mode,
            "check_return": False,
            "constructor": constructor_details,
            "resolved_target_constructor": None,
            "member_origin": member_origin,
            "failure_reason": failure_reason,
        }
        return _build_rule_result(
            rule,
            source,
            target_class,
            match,
            "FAILED",
            details,
            rule_evidence,
        )

    method_result = evaluate_method_compatibility(
        source_ctor,
        target_ctor,
        ctx=ctx,
        mode=mode,
        enforce_method_kind=False,
        check_return=False,
    )
    errors = method_result["errors"]
    status: RuleStatus = "OK" if not errors else "FAILED"
    reason = "Required constructor satisfied." if not errors else "; ".join(errors)
    details = {
        "reason": reason,
        "errors": errors,
        "expected": method_result["expected"],
        "found": method_result["found"],
        "mode": mode,
        "check_return": False,
        "constructor": constructor_details,
        "resolved_target_constructor": target_ctor.name,
        "member_origin": member_origin,
    }
    return _build_rule_result(
        rule,
        source,
        target_class,
        match,
        status,
        details,
        rule_evidence,
    )


class ApiSignatureEvaluator:
    """Evaluator for required API signature rules."""

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
        is_required_constructor_rule = rule.name == "required_constructor"
        is_required_factory_rule = rule.name == "required_factory"
        enforce_method_kind = bool(rule.params.get("enforce_method_kind", True))
        allow_missing = bool(rule.params.get("allow_missing", False))
        declared_only = bool(rule.params.get("declared_only", False))
        name_match = str(rule.params.get("name_match", "exact")).lower()
        aliases = rule.params.get("aliases")
        if isinstance(aliases, list):
            aliases = [str(alias) for alias in aliases]
        else:
            aliases = None
        pattern = rule.params.get("pattern")
        if pattern is not None:
            pattern = str(pattern)
        rule_evidence = (
            source_sig_ev,
            target_sig_ev,
            source_ann_ev,
            target_ann_ev,
        )

        if is_required_constructor_rule:
            return _evaluate_required_constructor_rule(
                rule,
                source,
                target,
                match,
                ctx=ctx,
                mode=mode,
                rule_evidence=rule_evidence,
            )

        if is_required_factory_rule:
            return _evaluate_required_factory_rule(
                rule,
                source,
                target,
                match,
                ctx=ctx,
                mode=mode,
                rule_evidence=rule_evidence,
                aliases=aliases,
                pattern=pattern,
            )

        if is_required_method_rule:
            target_class = _resolve_required_method_class(source, target, ctx=ctx)
            if name_match == "exact":
                if target_class is not None:
                    all_methods = {
                        member.name: member
                        for member in target_methods_for_class(
                            target_class,
                            ctx,
                            include_inherited=True,
                        )
                    }
                    declared_methods = {
                        member.name: member
                        for member in target_methods_for_class(
                            target_class,
                            ctx,
                            include_inherited=False,
                        )
                    }
                    member_origin = "missing"
                    resolved_target = None

                    if declared_only:
                        resolved_target = declared_methods.get(source.name)
                        if resolved_target is not None:
                            member_origin = "declared"
                        elif source.name in all_methods:
                            member_origin = "inherited"
                            details = {
                                "reason": (
                                    "method is inherited but not declared directly on "
                                    "target class"
                                ),
                                "errors": [
                                    "method is inherited but not declared directly on "
                                    "target class"
                                ],
                                "mode": mode,
                                "params_ignored": mode == "any",
                                "check_return": False,
                                "allow_missing": allow_missing,
                                "declared_only": True,
                                "member_resolution": "declared_only",
                                "member_origin": member_origin,
                            }
                            return _build_rule_result(
                                rule,
                                source,
                                target_class,
                                match,
                                "FAILED",
                                details,
                                rule_evidence,
                            )
                    else:
                        resolved_target = all_methods.get(source.name)
                        if resolved_target is not None:
                            member_origin = (
                                "declared"
                                if source.name in declared_methods
                                else "inherited"
                            )

                    if resolved_target is None:
                        if allow_missing and member_origin == "missing":
                            return _skip_optional_required_method(
                                rule,
                                source,
                                target_class,
                                match,
                                rule_evidence,
                                mode=mode,
                                declared_only=declared_only,
                                member_resolution=(
                                    "declared_only" if declared_only else "inherited_ok"
                                ),
                                member_origin=member_origin,
                            )
                        details = {
                            "reason": f"missing required method '{source.name}'",
                            "errors": [f"missing required method '{source.name}'"],
                            "mode": mode,
                            "params_ignored": mode == "any",
                            "check_return": False,
                            "allow_missing": allow_missing,
                            "declared_only": declared_only,
                            "member_resolution": (
                                "declared_only" if declared_only else "inherited_ok"
                            ),
                            "member_origin": member_origin,
                        }
                        return _build_rule_result(
                            rule,
                            source,
                            target_class,
                            match,
                            "FAILED",
                            details,
                            rule_evidence,
                        )

                    return _evaluate_required_method_against_candidate(
                        rule,
                        source,
                        resolved_target,
                        match,
                        rule_evidence,
                        ctx=ctx,
                        mode=mode,
                        check_return=check_return,
                        allow_missing=allow_missing,
                        declared_only=declared_only,
                        enforce_method_kind=enforce_method_kind,
                        member_resolution=(
                            "declared_only" if declared_only else "inherited_ok"
                        ),
                        member_origin=member_origin,
                    )
                if target.kind == "method":
                    return _evaluate_required_method_against_candidate(
                        rule,
                        source,
                        target,
                        match,
                        rule_evidence,
                        ctx=ctx,
                        mode=mode,
                        check_return=check_return,
                        allow_missing=allow_missing,
                        declared_only=declared_only,
                        enforce_method_kind=enforce_method_kind,
                        member_resolution="direct_match",
                        member_origin="declared",
                    )
            else:
                anchor_target = target_class or target
                if target_class is not None:
                    all_candidates = target_methods_for_class(
                        target_class,
                        ctx,
                        include_inherited=True,
                    )
                    declared_candidates = target_methods_for_class(
                        target_class,
                        ctx,
                        include_inherited=False,
                    )
                    candidate_pool = (
                        declared_candidates if declared_only else all_candidates
                    )
                    member_resolution = (
                        "declared_only_flexible"
                        if declared_only
                        else "inherited_ok_flexible"
                    )
                elif target.kind == "method":
                    all_candidates = [target]
                    declared_candidates = [target]
                    candidate_pool = [target]
                    member_resolution = "direct_match_flexible"
                else:
                    all_candidates = []
                    declared_candidates = []
                    candidate_pool = []
                    member_resolution = "flexible_missing_context"

                matching_candidates = filter_methods_by_name_match(
                    candidate_pool,
                    source_name=source.name,
                    name_match=name_match,
                    aliases=aliases,
                    pattern=pattern,
                )
                compatible_candidates: list[tuple[Entity, Dict[str, Any]]] = []
                for candidate in matching_candidates:
                    candidate_result = evaluate_method_compatibility(
                        source,
                        candidate,
                        ctx=ctx,
                        mode=mode,
                        enforce_method_kind=enforce_method_kind,
                        check_return=False,
                    )
                    if not candidate_result["errors"]:
                        compatible_candidates.append((candidate, candidate_result))

                candidate_names = sorted(
                    {candidate.name for candidate in matching_candidates}
                )
                compatible_candidate_names = [
                    candidate.name for candidate, _ in compatible_candidates
                ]

                if len(compatible_candidates) == 1:
                    resolved_target, _ = compatible_candidates[0]
                    member_origin = (
                        resolved_member_origin(resolved_target, target_class, ctx)
                        if target_class is not None
                        else "declared"
                    )
                    return _evaluate_required_method_against_candidate(
                        rule,
                        source,
                        resolved_target,
                        match,
                        rule_evidence,
                        ctx=ctx,
                        mode=mode,
                        check_return=check_return,
                        allow_missing=allow_missing,
                        declared_only=declared_only,
                        enforce_method_kind=enforce_method_kind,
                        member_resolution=member_resolution,
                        member_origin=member_origin,
                        details_extra={
                            "name_match": name_match,
                            "aliases": aliases,
                            "pattern": pattern,
                            "candidate_names": candidate_names,
                            "resolved_candidate": resolved_target.name,
                            "resolution_mode": name_match,
                            "ambiguity": None,
                        },
                    )

                if len(compatible_candidates) > 1:
                    details = {
                        "reason": (
                            "multiple compatible candidates matched flexible name "
                            "resolution"
                        ),
                        "errors": [
                            "multiple compatible candidates matched flexible name "
                            "resolution"
                        ],
                        "mode": mode,
                        "params_ignored": mode == "any",
                        "check_return": False,
                        "allow_missing": allow_missing,
                        "declared_only": declared_only,
                        "member_resolution": member_resolution,
                        "member_origin": "ambiguous",
                        "name_match": name_match,
                        "aliases": aliases,
                        "pattern": pattern,
                        "candidate_names": candidate_names,
                        "resolved_candidate": None,
                        "resolution_mode": name_match,
                        "failure_reason": "multiple_compatible_candidates",
                        "ambiguity": {
                            "compatible_candidates": compatible_candidate_names,
                        },
                    }
                    return _build_rule_result(
                        rule,
                        source,
                        anchor_target,
                        match,
                        "FAILED",
                        details,
                        rule_evidence,
                    )

                inherited_matching_candidates: list[Entity] = []
                if declared_only and target_class is not None:
                    declared_ids = {
                        candidate.canonical_id for candidate in declared_candidates
                    }
                    inherited_matching_candidates = [
                        candidate
                        for candidate in filter_methods_by_name_match(
                            all_candidates,
                            source_name=source.name,
                            name_match=name_match,
                            aliases=aliases,
                            pattern=pattern,
                        )
                        if candidate.canonical_id not in declared_ids
                    ]
                    if not matching_candidates and inherited_matching_candidates:
                        details = {
                            "reason": (
                                "method is inherited but not declared directly on "
                                "target class"
                            ),
                            "errors": [
                                "method is inherited but not declared directly on "
                                "target class"
                            ],
                            "mode": mode,
                            "params_ignored": mode == "any",
                            "check_return": False,
                            "allow_missing": allow_missing,
                            "declared_only": True,
                            "member_resolution": member_resolution,
                            "member_origin": "inherited",
                            "name_match": name_match,
                            "aliases": aliases,
                            "pattern": pattern,
                            "candidate_names": [],
                            "resolved_candidate": None,
                            "resolution_mode": name_match,
                            "failure_reason": "no_candidate_in_matched_class_context",
                            "ambiguity": None,
                        }
                        return _build_rule_result(
                            rule,
                            source,
                            target_class,
                            match,
                            "FAILED",
                            details,
                            rule_evidence,
                        )

                failure_reason = "no_candidate_in_matched_class_context"
                failure_message = (
                    "no candidate method matched within the matched target class "
                    "context"
                )
                if matching_candidates:
                    failure_reason = {
                        "alias": "no_compatible_candidate_for_aliases",
                        "regex": "no_compatible_candidate_for_pattern",
                        "any": "no_compatible_candidate_for_any_name",
                    }.get(name_match, "no_compatible_candidate")
                    failure_message = _flexible_match_reason(
                        name_match=name_match,
                        source_name=source.name,
                        aliases=aliases,
                        pattern=pattern,
                    )
                elif allow_missing:
                    return _skip_optional_required_method(
                        rule,
                        source,
                        anchor_target,
                        match,
                        rule_evidence,
                        mode=mode,
                        declared_only=declared_only,
                        member_resolution=member_resolution,
                        member_origin="missing",
                        details_extra={
                            "name_match": name_match,
                            "aliases": aliases,
                            "pattern": pattern,
                            "candidate_names": candidate_names,
                            "resolved_candidate": None,
                            "resolution_mode": name_match,
                            "failure_reason": "optional_member_absent",
                            "ambiguity": None,
                        },
                    )

                details = {
                    "reason": failure_message,
                    "errors": [failure_message],
                    "mode": mode,
                    "params_ignored": mode == "any",
                    "check_return": False,
                    "allow_missing": allow_missing,
                    "declared_only": declared_only,
                    "member_resolution": member_resolution,
                    "member_origin": "missing",
                    "name_match": name_match,
                    "aliases": aliases,
                    "pattern": pattern,
                    "candidate_names": candidate_names,
                    "resolved_candidate": None,
                    "resolution_mode": name_match,
                    "failure_reason": failure_reason,
                    "ambiguity": None,
                }
                return _build_rule_result(
                    rule,
                    source,
                    anchor_target,
                    match,
                    "FAILED",
                    details,
                    rule_evidence,
                )

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
            rule_evidence,
        )


__all__ = ["ApiSignatureEvaluator"]
