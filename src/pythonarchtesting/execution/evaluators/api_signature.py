from __future__ import annotations

from typing import Any, Dict, List

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

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
from .signature_comparison import compatible_compare as _compatible_compare
from .signature_comparison import (
    evaluate_method_compatibility,
)
from .signature_comparison import exact_compare as _exact_compare
from .signature_comparison import method_kind as _method_kind
from .signature_comparison import param_model as _param_model
from .signature_comparison import return_errors as _return_errors
from .signature_comparison import strip_method_receiver as _strip_method_receiver


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


def _skip_optional_signature_rule(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    evidence: tuple[Any, ...],
    *,
    details: dict[str, Any],
) -> RuleResult:
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
    allow_missing = bool(rule.params.get("allow_missing", False))
    name_match = str(rule.params.get("name_match", "any")).lower()
    target_class: Entity | None

    if target.kind == "class":
        target_class = target
    elif target.kind == "method":
        target_class = target_parent_class(target, ctx)
    else:
        target_class = matched_target_parent_class(source, ctx)

    if target_class is None:
        details: Dict[str, Any] = {
            "reason": "no_factory_candidate_found",
            "factory_rule": {
                "satisfy_with": satisfy_with,
                "allow_inherited": allow_inherited,
                "allow_missing": allow_missing,
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
                "allow_missing": allow_missing,
                "name_match": name_match,
                "aliases": aliases,
                "pattern": pattern,
            },
            "candidate_factories": candidate_details,
            "selected_candidate": None,
        }
        if allow_missing:
            details["reason"] = (
                "Optional factory is not present on target class under the current "
                "factory scope"
            )
            details["failure_reason"] = "optional_member_absent"
            return _skip_optional_signature_rule(
                rule,
                source,
                target_class,
                match,
                rule_evidence,
                details=details,
            )
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
                "allow_missing": allow_missing,
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
                "allow_missing": allow_missing,
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
            "allow_missing": allow_missing,
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
    allow_missing = bool(rule.params.get("allow_missing", False))
    expected_source_id = rule.params.get("expected_source_constructor_id")

    constructor_details = {
        "kind": constructor_kind,
        "resolved_kind": resolved_kind,
        "allow_inherited": allow_inherited,
        "allow_missing": allow_missing,
    }

    target_class: Entity | None = target if target.kind == "class" else None
    if target_class is None:
        details = {
            "reason": "required_constructor requires a matched target class",
            "errors": ["required_constructor requires a matched target class"],
            "mode": mode,
            "check_return": False,
            "allow_missing": allow_missing,
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
            "allow_missing": allow_missing,
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
        if allow_missing:
            details = {
                "reason": (
                    f"Optional constructor '{resolved_kind}' is not present on "
                    "target class"
                ),
                "errors": [],
                "mode": mode,
                "check_return": False,
                "allow_missing": True,
                "constructor": constructor_details,
                "resolved_target_constructor": None,
                "member_origin": "missing",
                "failure_reason": "optional_member_absent",
            }
            return _skip_optional_signature_rule(
                rule,
                source,
                target_class,
                match,
                rule_evidence,
                details=details,
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
            "allow_missing": allow_missing,
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
        "allow_missing": allow_missing,
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
