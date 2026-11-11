from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, NamedTuple

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

from .annotation_compatibility import compare_annotation_text
from .construction_resolution import (
    constructor_candidates_for_class,
    resolve_target_constructor,
)
from .factory_resolution import (
    StaticAttributeFactoryCandidate,
    factory_candidate_origin,
    factory_candidates_for_class,
    factory_kind,
    filter_factory_candidates,
    filter_static_attribute_factory_candidates,
    static_attribute_factory_candidates_for_class,
)
from .member_name_resolution import (
    filter_methods_by_name_match,
    matched_target_parent_class,
)
from .member_name_resolution import member_origin as resolved_member_origin
from .member_name_resolution import target_methods_for_class, target_parent_class
from .messages import build_rule_result
from .signature_comparison import compatible_compare as _compatible_compare
from .signature_comparison import evaluate_method_compatibility
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
    return build_rule_result(
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
    return build_rule_result(
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
    return build_rule_result(
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


def _unwrap_string_annotation(annotation: str | None) -> str | None:
    if annotation is None:
        return None
    text = str(annotation).strip()
    if not text:
        return None
    try:
        parsed = ast.parse(text, mode="eval").body
    except SyntaxError:
        return text
    if isinstance(parsed, ast.Constant) and isinstance(parsed.value, str):
        return parsed.value.strip() or None
    return text


def _normalize_factory_return_annotation(
    annotation: str | None,
    *,
    target_class: Entity,
) -> str | None:
    text = _unwrap_string_annotation(annotation)
    if text is None:
        return None
    if text in {
        "Self",
        "typing.Self",
        "typing_extensions.Self",
        target_class.name,
        target_class.qualname,
    }:
        return target_class.name
    return text


def _factory_return_mismatch(
    candidate: Entity,
    *,
    target_class: Entity,
    ctx: EvalContext,
    return_annotation_mode: str,
    detection_mode: str,
) -> tuple[str | None, list[str]]:
    if factory_kind(candidate, detection_mode=detection_mode) == "constructor":
        return None, []

    candidate_return = _normalize_factory_return_annotation(
        _param_model(candidate).get("return_annotation"),
        target_class=target_class,
    )
    if candidate_return is None:
        return (
            "factory_return_annotation_missing",
            ["factory candidate is missing a return annotation"],
        )

    comparison = compare_annotation_text(
        expected=target_class.name,
        found=candidate_return,
        expected_entity=target_class,
        found_entity=candidate,
        ctx=ctx,
        variance="invariant" if return_annotation_mode == "exact" else "covariant",
    )
    if comparison.compatible:
        return None, []
    if return_annotation_mode == "exact":
        return (
            "factory_return_annotation_exact_mismatch",
            [
                "factory return annotation mismatch: "
                f"expected {comparison.expected}, found {comparison.found}"
            ],
        )
    return (
        "factory_return_annotation_incompatible",
        [
            "factory return annotation mismatch: "
            f"expected {comparison.expected}, found {comparison.found}"
        ],
    )


def _static_attribute_candidate_qualname(
    candidate: StaticAttributeFactoryCandidate,
) -> str:
    return f"{candidate.owner_class.qualname}.{candidate.name}"


def _static_attribute_param_errors(
    source: Entity,
    *,
    mode: str,
) -> list[str]:
    if mode == "any":
        return []

    source_model = _param_model(source)
    source_params = _strip_method_receiver(source_model.get("params", []), source)
    if source_params or source_model.get("vararg") or source_model.get("kwarg"):
        return [
            "static attribute factory cannot satisfy a parameterized factory signature"
        ]
    return []


def _static_attribute_return_mismatch(
    candidate: StaticAttributeFactoryCandidate,
    *,
    target_class: Entity,
    ctx: EvalContext,
    return_annotation_mode: str,
) -> tuple[str | None, list[str]]:
    candidate_annotation = _normalize_factory_return_annotation(
        candidate.annotation,
        target_class=target_class,
    )
    if candidate_annotation is None:
        return (
            "factory_static_attribute_annotation_missing",
            [
                "static attribute factory candidate is missing a "
                "class-compatible annotation"
            ],
        )

    comparison = compare_annotation_text(
        expected=target_class.name,
        found=candidate_annotation,
        expected_entity=target_class,
        found_entity=candidate.owner_class,
        ctx=ctx,
        variance="invariant" if return_annotation_mode == "exact" else "covariant",
    )
    if comparison.compatible:
        return None, []
    return (
        "factory_static_attribute_annotation_incompatible",
        [
            "static attribute factory annotation mismatch: "
            f"expected {comparison.expected}, found {comparison.found}"
        ],
    )


@dataclass(frozen=True)
class _FactoryRuleParams:
    """The ``required_factory`` parameters, read once per evaluation."""

    satisfy_with: list[str]
    allow_inherited: bool
    allow_missing: bool
    name_match: str
    aliases: list[str] | None
    pattern: str | None
    detection_mode: str
    check_return: bool
    return_annotation_mode: str

    @classmethod
    def from_rule(
        cls,
        rule: Rule,
        *,
        aliases: list[str] | None,
        pattern: str | None,
    ) -> _FactoryRuleParams:
        return cls(
            satisfy_with=[
                str(value)
                for value in rule.params.get(
                    "satisfy_with",
                    ["constructor", "classmethod", "staticmethod"],
                )
            ],
            allow_inherited=bool(rule.params.get("allow_inherited", True)),
            allow_missing=bool(rule.params.get("allow_missing", False)),
            name_match=str(rule.params.get("name_match", "any")).lower(),
            aliases=aliases,
            pattern=pattern,
            detection_mode=str(rule.params.get("detection_mode", "strict")).lower(),
            check_return=bool(rule.params.get("check_return", False)),
            return_annotation_mode=str(
                rule.params.get("return_annotation_mode", "ignore")
            ).lower(),
        )

    @property
    def checks_return_annotation(self) -> bool:
        return self.check_return and self.return_annotation_mode != "ignore"

    def as_details(self) -> dict[str, Any]:
        return {
            "satisfy_with": self.satisfy_with,
            "allow_inherited": self.allow_inherited,
            "allow_missing": self.allow_missing,
            "name_match": self.name_match,
            "aliases": self.aliases,
            "pattern": self.pattern,
            "detection_mode": self.detection_mode,
            "check_return": self.check_return,
            "return_annotation_mode": self.return_annotation_mode,
        }


@dataclass
class _FactoryCheckState:
    """What checking the accepted factory candidates found."""

    compatible: list[dict[str, Any]] = field(default_factory=list)
    signature_compatible: int = 0
    return_failure_reasons: list[str] = field(default_factory=list)

    def record_return_check(self, failure_reason: str | None) -> None:
        if failure_reason is not None:
            self.return_failure_reasons.append(failure_reason)


def _factory_details(
    reason: str,
    *,
    mode: str,
    params: _FactoryRuleParams,
    candidate_factories: list[dict[str, Any]],
    selected_candidate: dict[str, Any] | None,
) -> Dict[str, Any]:
    return {
        "reason": reason,
        "params_ignored": mode == "any",
        "factory_rule": params.as_details(),
        "candidate_factories": candidate_factories,
        "selected_candidate": selected_candidate,
    }


def _resolve_factory_class(
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> Entity | None:
    if target.kind == "class":
        return target
    if target.kind == "method":
        return target_parent_class(target, ctx)
    return matched_target_parent_class(source, ctx)


def _static_attribute_candidates(
    source: Entity,
    target_class: Entity,
    ctx: EvalContext,
    params: _FactoryRuleParams,
) -> tuple[
    list[StaticAttributeFactoryCandidate],
    list[StaticAttributeFactoryCandidate],
    list[StaticAttributeFactoryCandidate],
]:
    """All, name-matched and accepted static attribute factory candidates."""
    if "static_attribute" not in params.satisfy_with:
        return [], [], []
    all_candidates = static_attribute_factory_candidates_for_class(
        target_class,
        ctx,
        allow_inherited=True,
    )
    matched = filter_static_attribute_factory_candidates(
        all_candidates,
        name_match=params.name_match,
        source_name=source.name,
        aliases=params.aliases,
        pattern=params.pattern,
    )
    filtered = [
        candidate
        for candidate in matched
        if params.allow_inherited or not candidate.inherited
    ]
    return all_candidates, matched, filtered


def _describe_method_candidates(
    candidates: list[Entity],
    filtered_candidates: list[Entity],
    target_class: Entity,
    ctx: EvalContext,
    params: _FactoryRuleParams,
    details_by_key: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    described: list[dict[str, Any]] = []
    for candidate in candidates:
        accepted = candidate in filtered_candidates
        detail = {
            "entity_id": candidate.canonical_id,
            "qualname": candidate.qualname,
            "name": candidate.name,
            "factory_kind": factory_kind(
                candidate, detection_mode=params.detection_mode
            ),
            "method_kind": _method_kind(
                candidate,
                detection_mode=params.detection_mode,
            ),
            "inherited": factory_candidate_origin(candidate, target_class, ctx)
            != "declared",
            "accepted": accepted,
            "failure_reason": None,
            "errors": (
                [] if accepted else ["filtered out by satisfy_with or name_match"]
            ),
        }
        described.append(detail)
        details_by_key[("entity", candidate.canonical_id)] = detail
    return described


def _static_attribute_filter_outcome(
    candidate: StaticAttributeFactoryCandidate,
    *,
    matched: bool,
    allow_inherited: bool,
) -> tuple[str | None, list[str]]:
    if matched and candidate.inherited and not allow_inherited:
        return (
            "static_attribute_inherited_not_allowed",
            [
                "static attribute is inherited but not declared directly on target "
                "class"
            ],
        )
    if matched:
        return None, []
    return None, ["filtered out by name_match"]


def _describe_static_attribute_candidates(
    all_candidates: list[StaticAttributeFactoryCandidate],
    matched_candidates: list[StaticAttributeFactoryCandidate],
    filtered_candidates: list[StaticAttributeFactoryCandidate],
    params: _FactoryRuleParams,
    details_by_key: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    described: list[dict[str, Any]] = []
    for static_candidate in all_candidates:
        qualname = _static_attribute_candidate_qualname(static_candidate)
        failure_reason, errors = _static_attribute_filter_outcome(
            static_candidate,
            matched=static_candidate in matched_candidates,
            allow_inherited=params.allow_inherited,
        )
        detail = {
            "entity_id": None,
            "qualname": qualname,
            "name": static_candidate.name,
            "factory_kind": "static_attribute",
            "method_kind": None,
            "inherited": static_candidate.inherited,
            "accepted": static_candidate in filtered_candidates,
            "failure_reason": failure_reason,
            "errors": errors,
            "annotation": static_candidate.annotation,
            "value_expr": static_candidate.value_expr,
            "lineno": static_candidate.lineno,
        }
        described.append(detail)
        details_by_key[("static_attribute", qualname)] = detail
    return described


def _record_candidate_outcome(
    detail: dict[str, Any],
    errors: list[str],
    failure_reason: str | None,
) -> None:
    detail["accepted"] = not errors
    detail["failure_reason"] = failure_reason
    detail["errors"] = errors


def _check_method_candidates(
    source: Entity,
    filtered_candidates: list[Entity],
    target_class: Entity,
    *,
    ctx: EvalContext,
    mode: str,
    params: _FactoryRuleParams,
    details_by_key: dict[tuple[str, str], dict[str, Any]],
    state: _FactoryCheckState,
) -> None:
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
        failure_reason = None
        if not errors:
            state.signature_compatible += 1
            if params.checks_return_annotation:
                failure_reason, return_errors = _factory_return_mismatch(
                    candidate,
                    target_class=target_class,
                    ctx=ctx,
                    return_annotation_mode=params.return_annotation_mode,
                    detection_mode=params.detection_mode,
                )
                errors.extend(return_errors)
                state.record_return_check(failure_reason)
        _record_candidate_outcome(
            details_by_key[("entity", candidate.canonical_id)],
            errors,
            failure_reason,
        )
        if not errors:
            state.compatible.append(
                {
                    "factory_kind": factory_kind(
                        candidate,
                        detection_mode=params.detection_mode,
                    ),
                    "candidate": candidate,
                }
            )


def _check_static_attribute_candidates(
    source: Entity,
    filtered_candidates: list[StaticAttributeFactoryCandidate],
    target_class: Entity,
    *,
    ctx: EvalContext,
    mode: str,
    params: _FactoryRuleParams,
    details_by_key: dict[tuple[str, str], dict[str, Any]],
    state: _FactoryCheckState,
) -> None:
    for static_candidate in filtered_candidates:
        errors = _static_attribute_param_errors(source, mode=mode)
        failure_reason = None
        if not errors:
            state.signature_compatible += 1
            if params.checks_return_annotation:
                failure_reason, return_errors = _static_attribute_return_mismatch(
                    static_candidate,
                    target_class=target_class,
                    ctx=ctx,
                    return_annotation_mode=params.return_annotation_mode,
                )
                errors.extend(return_errors)
                state.record_return_check(failure_reason)
        else:
            failure_reason = "static_attribute_parameterized_factory_mismatch"
        qualname = _static_attribute_candidate_qualname(static_candidate)
        _record_candidate_outcome(
            details_by_key[("static_attribute", qualname)],
            errors,
            failure_reason,
        )
        if not errors:
            state.compatible.append(
                {
                    "factory_kind": "static_attribute",
                    "candidate": static_candidate,
                }
            )


def _aggregate_failure_reason(
    state: _FactoryCheckState,
    candidate_details: list[dict[str, Any]],
) -> str:
    unique_return_reasons = set(state.return_failure_reasons)
    if state.signature_compatible and len(unique_return_reasons) == 1:
        return next(iter(unique_return_reasons))
    candidate_failure_reasons = {
        str(item["failure_reason"])
        for item in candidate_details
        if item.get("failure_reason")
    }
    if len(candidate_failure_reasons) == 1:
        return next(iter(candidate_failure_reasons))
    return "no_compatible_factory_candidate"


def _selected_details(
    selected_candidate: dict[str, Any],
    target_class: Entity,
) -> tuple[Entity, dict[str, Any]]:
    """The entity a passing factory result points at, and its details."""
    selected_factory_kind = str(selected_candidate["factory_kind"])
    if selected_factory_kind == "static_attribute":
        selected_static_attribute = selected_candidate["candidate"]
        return target_class, {
            "entity_id": None,
            "qualname": _static_attribute_candidate_qualname(selected_static_attribute),
            "name": selected_static_attribute.name,
            "factory_kind": "static_attribute",
            "owner_class": selected_static_attribute.owner_class.qualname,
            "annotation": selected_static_attribute.annotation,
        }
    selected_method_candidate = selected_candidate["candidate"]
    return selected_method_candidate, {
        "entity_id": selected_method_candidate.canonical_id,
        "qualname": selected_method_candidate.qualname,
        "name": selected_method_candidate.name,
        "factory_kind": selected_factory_kind,
    }


def _missing_factory_result(
    rule: Rule,
    source: Entity,
    target_class: Entity,
    match: MatchResult,
    rule_evidence: tuple[Any, ...],
    details: Dict[str, Any],
    *,
    allow_missing: bool,
) -> RuleResult:
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
    return build_rule_result(
        rule,
        source,
        target_class,
        match,
        "FAILED",
        details,
        rule_evidence,
    )


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
    params = _FactoryRuleParams.from_rule(rule, aliases=aliases, pattern=pattern)
    target_class = _resolve_factory_class(source, target, ctx)
    if target_class is None:
        details = _factory_details(
            "no_factory_candidate_found",
            mode=mode,
            params=params,
            candidate_factories=[],
            selected_candidate=None,
        )
        return build_rule_result(
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
        allow_inherited=params.allow_inherited,
        detection_mode=params.detection_mode,
    )
    filtered_candidates = filter_factory_candidates(
        candidates,
        satisfy_with=params.satisfy_with,
        name_match=params.name_match,
        source_name=source.extras.get("assignment_wrapped_by") or source.name,
        aliases=params.aliases,
        pattern=params.pattern,
        detection_mode=params.detection_mode,
    )
    static_candidates, matched_static, filtered_static = _static_attribute_candidates(
        source, target_class, ctx, params
    )

    details_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    candidate_details = _describe_method_candidates(
        candidates, filtered_candidates, target_class, ctx, params, details_by_key
    ) + _describe_static_attribute_candidates(
        static_candidates, matched_static, filtered_static, params, details_by_key
    )

    if not filtered_candidates and not filtered_static:
        return _missing_factory_result(
            rule,
            source,
            target_class,
            match,
            rule_evidence,
            _factory_details(
                "no_factory_candidate_found",
                mode=mode,
                params=params,
                candidate_factories=candidate_details,
                selected_candidate=None,
            ),
            allow_missing=params.allow_missing,
        )

    state = _FactoryCheckState()
    _check_method_candidates(
        source,
        filtered_candidates,
        target_class,
        ctx=ctx,
        mode=mode,
        params=params,
        details_by_key=details_by_key,
        state=state,
    )
    _check_static_attribute_candidates(
        source,
        filtered_static,
        target_class,
        ctx=ctx,
        mode=mode,
        params=params,
        details_by_key=details_by_key,
        state=state,
    )

    if len(state.compatible) != 1:
        reason = (
            _aggregate_failure_reason(state, candidate_details)
            if not state.compatible
            else "multiple_compatible_factory_candidates"
        )
        details = _factory_details(
            reason,
            mode=mode,
            params=params,
            candidate_factories=candidate_details,
            selected_candidate=None,
        )
        return build_rule_result(
            rule,
            source,
            target_class,
            match,
            "FAILED",
            details,
            rule_evidence,
        )

    selected_entity, selected_candidate_details = _selected_details(
        state.compatible[0], target_class
    )
    details = _factory_details(
        "Factory requirement satisfied.",
        mode=mode,
        params=params,
        candidate_factories=candidate_details,
        selected_candidate=selected_candidate_details,
    )
    return build_rule_result(
        rule,
        source,
        selected_entity,
        match,
        "OK",
        details,
        rule_evidence,
    )


@dataclass(frozen=True)
class _ConstructorRuleParams:
    """The ``required_constructor`` parameters, read once per evaluation."""

    kind: str
    resolved_kind: str
    allow_inherited: bool
    allow_missing: bool

    @classmethod
    def from_rule(cls, rule: Rule) -> _ConstructorRuleParams:
        kind = str(rule.params.get("constructor_kind", "auto")).lower()
        return cls(
            kind=kind,
            resolved_kind=str(
                rule.params.get("resolved_constructor_kind", kind)
            ).lower(),
            allow_inherited=bool(rule.params.get("allow_inherited", True)),
            allow_missing=bool(rule.params.get("allow_missing", False)),
        )

    @property
    def method_name(self) -> Literal["__init__", "__new__"]:
        """The constructor method the target class has to provide."""
        return "__new__" if self.resolved_kind == "__new__" else "__init__"

    def as_details(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "resolved_kind": self.resolved_kind,
            "allow_inherited": self.allow_inherited,
            "allow_missing": self.allow_missing,
        }


def _constructor_details(
    reason: str,
    errors: list[str],
    *,
    mode: str,
    params: _ConstructorRuleParams,
    member_origin: str = "missing",
    resolved_target_constructor: str | None = None,
    comparison: dict[str, Any] | None = None,
    failure_reason: str | None = None,
) -> Dict[str, Any]:
    """The details of a constructor verdict, keys in the order reported.

    ``comparison`` (``expected`` and ``found``) is present only when two
    constructors were compared, ``failure_reason`` only when the target has
    no usable constructor.
    """
    details: Dict[str, Any] = {
        "reason": reason,
        "errors": errors,
        **(comparison or {}),
        "mode": mode,
        "params_ignored": mode == "any",
        "check_return": False,
        "allow_missing": params.allow_missing,
        "constructor": params.as_details(),
        "resolved_target_constructor": resolved_target_constructor,
        "member_origin": member_origin,
    }
    if failure_reason is not None:
        details["failure_reason"] = failure_reason
    return details


def _not_a_class_result(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    rule_evidence: tuple[Any, ...],
    *,
    mode: str,
    params: _ConstructorRuleParams,
) -> RuleResult:
    """Fail a constructor rule whose source class matched something else."""
    reason = "required_constructor requires a matched target class"
    details = _constructor_details(reason, [reason], mode=mode, params=params)
    return build_rule_result(
        rule,
        source,
        target,
        match,
        "FAILED",
        details,
        rule_evidence,
    )


def _synthetic_source_constructor(rule: Rule, ctx: EvalContext) -> Entity | None:
    """The generated reference constructor the compiler described, if any.

    A generated constructor, such as a dataclass ``__init__``, has no entity
    of its own; the compiler records its class and parameter model instead,
    and the method is rebuilt from them here.
    """
    source_model = rule.params.get("expected_source_constructor_model")
    source_context_id = rule.params.get("expected_source_constructor_context_id")
    source_origin = str(
        rule.params.get(
            "source_constructor_origin",
            "generated_dataclass_init",
        )
    )
    source_context = (
        ctx.source_by_id.get(str(source_context_id))
        if source_context_id is not None
        else None
    )
    if (
        not isinstance(source_context, Entity)
        or source_context.kind != "class"
        or not isinstance(source_model, dict)
    ):
        return None

    from .construction_resolution import build_synthetic_constructor_entity

    return build_synthetic_constructor_entity(
        source_context,
        name="__init__",
        origin=source_origin,  # type: ignore[arg-type]
        inherited=False,
        param_model=source_model,
    )


def _resolve_source_constructor(rule: Rule, ctx: EvalContext) -> Entity | None:
    """The reference constructor the target's is compared with, or None.

    A declared constructor is named by its id; an id that resolves to no
    method falls back to the generated constructor's model.
    """
    expected_source_id = rule.params.get("expected_source_constructor_id")
    if expected_source_id is not None:
        resolved_source = ctx.source_by_id.get(str(expected_source_id))
        if isinstance(resolved_source, Entity) and resolved_source.kind == "method":
            return resolved_source
    source_ctor = _synthetic_source_constructor(rule, ctx)
    if not isinstance(source_ctor, Entity) or source_ctor.kind != "method":
        return None
    return source_ctor


def _only_inherited(
    target_class: Entity,
    target_entities: Any,
    method_name: Literal["__init__", "__new__"],
) -> bool:
    """Whether the class has the constructor only from a base class."""
    return any(
        candidate.kind == method_name and candidate.inherited
        for candidate in constructor_candidates_for_class(
            target_class,
            target_entities,
            allow_inherited=True,
        )
    )


def _missing_constructor_result(
    rule: Rule,
    source: Entity,
    target_class: Entity,
    match: MatchResult,
    rule_evidence: tuple[Any, ...],
    *,
    mode: str,
    params: _ConstructorRuleParams,
    member_origin: str,
    inherited_only: bool,
) -> RuleResult:
    """Skip or fail a rule whose target class has no usable constructor.

    An optional constructor is skipped. A required one fails, and the reason
    says whether the class has none or only inherits one it may not.
    """
    if params.allow_missing:
        details = _constructor_details(
            f"Optional constructor '{params.resolved_kind}' is not present on "
            "target class",
            [],
            mode=mode,
            params=params,
            failure_reason="optional_member_absent",
        )
        return _skip_optional_signature_rule(
            rule,
            source,
            target_class,
            match,
            rule_evidence,
            details=details,
        )
    if inherited_only and not params.allow_inherited:
        reason = "constructor is inherited but not declared directly on target class"
        member_origin = "inherited"
        failure_reason = "constructor_inherited_not_allowed"
    else:
        reason = f"missing required constructor '{params.resolved_kind}'"
        failure_reason = "missing_constructor"
    details = _constructor_details(
        reason,
        [reason],
        mode=mode,
        params=params,
        member_origin=member_origin,
        failure_reason=failure_reason,
    )
    return build_rule_result(
        rule,
        source,
        target_class,
        match,
        "FAILED",
        details,
        rule_evidence,
    )


def _compared_constructor_result(
    rule: Rule,
    source: Entity,
    target_class: Entity,
    match: MatchResult,
    rule_evidence: tuple[Any, ...],
    *,
    ctx: EvalContext,
    mode: str,
    params: _ConstructorRuleParams,
    source_ctor: Entity,
    target_ctor: Entity,
    member_origin: str,
) -> RuleResult:
    """Judge the target's constructor against the reference's signature.

    Neither the method kind nor the return is compared: only the parameters
    say whether the class is built the same way.
    """
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
    details = _constructor_details(
        reason,
        errors,
        mode=mode,
        params=params,
        member_origin=member_origin,
        resolved_target_constructor=target_ctor.name,
        comparison={
            "expected": method_result["expected"],
            "found": method_result["found"],
        },
    )
    return build_rule_result(
        rule,
        source,
        target_class,
        match,
        status,
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
    """Check that the matched class is constructed like the reference class.

    The match has to be a class; the compiler has to have resolved the
    reference constructor; the target class has to provide the required
    ``__init__`` or ``__new__`` (declared, or inherited when allowed); and
    its parameters have to fit the reference's under ``mode``.
    """
    params = _ConstructorRuleParams.from_rule(rule)
    if target.kind != "class":
        return _not_a_class_result(
            rule, source, target, match, rule_evidence, mode=mode, params=params
        )
    target_class = target

    source_ctor = _resolve_source_constructor(rule, ctx)
    if source_ctor is None:
        reason = (
            "compiler did not resolve a source constructor for required_constructor"
        )
        return build_rule_result(
            rule,
            source,
            target_class,
            match,
            "FAILED",
            _constructor_details(reason, [reason], mode=mode, params=params),
            rule_evidence,
        )

    target_entities = ctx.target_index.all_sorted
    target_candidate = resolve_target_constructor(
        target_class,
        target_entities,
        constructor_kind=params.method_name,
        allow_inherited=params.allow_inherited,
    )
    target_ctor = target_candidate.entity if target_candidate is not None else None
    member_origin = "missing"
    if target_candidate is not None:
        member_origin = "inherited" if target_candidate.inherited else "declared"

    if target_ctor is None:
        return _missing_constructor_result(
            rule,
            source,
            target_class,
            match,
            rule_evidence,
            mode=mode,
            params=params,
            member_origin=member_origin,
            inherited_only=_only_inherited(
                target_class, target_entities, params.method_name
            ),
        )
    return _compared_constructor_result(
        rule,
        source,
        target_class,
        match,
        rule_evidence,
        ctx=ctx,
        mode=mode,
        params=params,
        source_ctor=source_ctor,
        target_ctor=target_ctor,
        member_origin=member_origin,
    )


@dataclass(frozen=True)
class _SignatureRuleParams:
    """The parameters every ``api_signature`` rule reads, read once."""

    mode: str
    allow_extra: bool
    allow_rename: bool
    return_only: bool
    check_return: bool
    enforce_method_kind: bool
    allow_missing: bool
    declared_only: bool
    name_match: str
    aliases: list[str] | None
    pattern: str | None

    @classmethod
    def from_rule(cls, rule: Rule) -> _SignatureRuleParams:
        """Read the parameters, the aliases and the pattern stripped.

        Surrounding whitespace can never be part of a method name, so it is
        dropped, as ``does_not_have`` drops it; otherwise a pattern or an
        alias with a trailing space would silently match nothing.
        """
        aliases = rule.params.get("aliases")
        pattern = rule.params.get("pattern")
        return cls(
            mode=str(rule.params.get("mode", "compatible")).lower(),
            allow_extra=bool(rule.params.get("allow_extra_params", True)),
            allow_rename=bool(rule.params.get("allow_param_rename", False)),
            return_only=bool(rule.params.get("return_only", False)),
            check_return=bool(rule.params.get("check_return", False)),
            enforce_method_kind=bool(rule.params.get("enforce_method_kind", True)),
            allow_missing=bool(rule.params.get("allow_missing", False)),
            declared_only=bool(rule.params.get("declared_only", False)),
            name_match=str(rule.params.get("name_match", "exact")).lower(),
            aliases=(
                [str(alias).strip() for alias in aliases]
                if isinstance(aliases, list)
                else None
            ),
            pattern=str(pattern).strip() if pattern is not None else None,
        )

    @property
    def exact_member_resolution(self) -> str:
        return "declared_only" if self.declared_only else "inherited_ok"


class _FlexiblePool(NamedTuple):
    """Where flexible name resolution looks for a required method."""

    all_candidates: list[Entity]
    declared_candidates: list[Entity]
    candidate_pool: list[Entity]
    member_resolution: str


def _method_failure_details(
    message: str,
    params: _SignatureRuleParams,
    *,
    member_resolution: str,
    member_origin: str,
    flexible: dict[str, Any] | None = None,
) -> dict[str, Any]:
    details = {
        "reason": message,
        "errors": [message],
        "mode": params.mode,
        "params_ignored": params.mode == "any",
        "check_return": False,
        "allow_missing": params.allow_missing,
        "declared_only": params.declared_only,
        "member_resolution": member_resolution,
        "member_origin": member_origin,
    }
    if flexible:
        details.update(flexible)
    return details


def _flexible_details(
    params: _SignatureRuleParams,
    *,
    candidate_names: list[str],
    resolved_candidate: str | None,
    ambiguity: dict[str, Any] | None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "name_match": params.name_match,
        "aliases": params.aliases,
        "pattern": params.pattern,
        "candidate_names": candidate_names,
        "resolved_candidate": resolved_candidate,
        "resolution_mode": params.name_match,
    }
    if failure_reason is not None:
        details["failure_reason"] = failure_reason
    details["ambiguity"] = ambiguity
    return details


def _failed_method_result(
    rule: Rule,
    source: Entity,
    anchor: Entity,
    match: MatchResult,
    evidence: tuple[Any, ...],
    details: dict[str, Any],
) -> RuleResult:
    return build_rule_result(
        rule,
        source,
        anchor,
        match,
        "FAILED",
        details,
        evidence,
    )


def _lookup_exact_member(
    source_name: str,
    target_class: Entity,
    ctx: EvalContext,
    *,
    declared_only: bool,
) -> tuple[Entity | None, str]:
    """The method named like the reference, and where it comes from.

    ``(None, "inherited")`` means ``declared_only`` found it only inherited.
    """
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
    if declared_only:
        resolved = declared_methods.get(source_name)
        if resolved is not None:
            return resolved, "declared"
        if source_name in all_methods:
            return None, "inherited"
        return None, "missing"
    resolved = all_methods.get(source_name)
    if resolved is None:
        return None, "missing"
    return resolved, "declared" if source_name in declared_methods else "inherited"


def _evaluate_exact_method_in_class(
    rule: Rule,
    source: Entity,
    target_class: Entity,
    match: MatchResult,
    evidence: tuple[Any, ...],
    *,
    ctx: EvalContext,
    params: _SignatureRuleParams,
) -> RuleResult:
    member_resolution = params.exact_member_resolution
    resolved_target, member_origin = _lookup_exact_member(
        source.name, target_class, ctx, declared_only=params.declared_only
    )
    if resolved_target is not None:
        return _evaluate_required_method_against_candidate(
            rule,
            source,
            resolved_target,
            match,
            evidence,
            ctx=ctx,
            mode=params.mode,
            check_return=params.check_return,
            allow_missing=params.allow_missing,
            declared_only=params.declared_only,
            enforce_method_kind=params.enforce_method_kind,
            member_resolution=member_resolution,
            member_origin=member_origin,
        )
    if member_origin == "inherited":
        message = "method is inherited but not declared directly on target class"
    elif params.allow_missing:
        return _skip_optional_required_method(
            rule,
            source,
            target_class,
            match,
            evidence,
            mode=params.mode,
            declared_only=params.declared_only,
            member_resolution=member_resolution,
            member_origin=member_origin,
        )
    else:
        message = f"missing required method '{source.name}'"
    details = _method_failure_details(
        message,
        params,
        member_resolution=member_resolution,
        member_origin=member_origin,
    )
    return _failed_method_result(rule, source, target_class, match, evidence, details)


def _evaluate_required_method_exact(
    rule: Rule,
    source: Entity,
    target: Entity,
    target_class: Entity | None,
    match: MatchResult,
    evidence: tuple[Any, ...],
    *,
    ctx: EvalContext,
    params: _SignatureRuleParams,
) -> RuleResult | None:
    """``None`` means no class and no method to check: compare signatures."""
    if target_class is not None:
        return _evaluate_exact_method_in_class(
            rule, source, target_class, match, evidence, ctx=ctx, params=params
        )
    if target.kind != "method":
        return None
    return _evaluate_required_method_against_candidate(
        rule,
        source,
        target,
        match,
        evidence,
        ctx=ctx,
        mode=params.mode,
        check_return=params.check_return,
        allow_missing=params.allow_missing,
        declared_only=params.declared_only,
        enforce_method_kind=params.enforce_method_kind,
        member_resolution="direct_match",
        member_origin="declared",
    )


def _flexible_candidate_pool(
    target: Entity,
    target_class: Entity | None,
    ctx: EvalContext,
    *,
    declared_only: bool,
) -> _FlexiblePool:
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
        if declared_only:
            return _FlexiblePool(
                all_candidates,
                declared_candidates,
                declared_candidates,
                "declared_only_flexible",
            )
        return _FlexiblePool(
            all_candidates,
            declared_candidates,
            all_candidates,
            "inherited_ok_flexible",
        )
    if target.kind == "method":
        return _FlexiblePool([target], [target], [target], "direct_match_flexible")
    return _FlexiblePool([], [], [], "flexible_missing_context")


def _filter_by_flexible_name(
    candidates: list[Entity],
    source: Entity,
    params: _SignatureRuleParams,
) -> list[Entity]:
    return filter_methods_by_name_match(
        candidates,
        source_name=source.name,
        name_match=params.name_match,
        aliases=params.aliases,
        pattern=params.pattern,
    )


def _compatible_flexible_candidates(
    source: Entity,
    candidates: list[Entity],
    *,
    ctx: EvalContext,
    params: _SignatureRuleParams,
) -> list[Entity]:
    compatible: list[Entity] = []
    for candidate in candidates:
        candidate_result = evaluate_method_compatibility(
            source,
            candidate,
            ctx=ctx,
            mode=params.mode,
            enforce_method_kind=params.enforce_method_kind,
            check_return=False,
        )
        if not candidate_result["errors"]:
            compatible.append(candidate)
    return compatible


def _only_inherited_flexible_match(
    source: Entity,
    pool: _FlexiblePool,
    matching_candidates: list[Entity],
    target_class: Entity | None,
    params: _SignatureRuleParams,
) -> bool:
    """Under ``declared_only``, did only an inherited method match the name?"""
    if not params.declared_only or target_class is None:
        return False
    declared_ids = {candidate.canonical_id for candidate in pool.declared_candidates}
    inherited_matching_candidates = [
        candidate
        for candidate in _filter_by_flexible_name(pool.all_candidates, source, params)
        if candidate.canonical_id not in declared_ids
    ]
    return not matching_candidates and bool(inherited_matching_candidates)


def _flexible_no_compatible_result(
    rule: Rule,
    source: Entity,
    anchor: Entity,
    match: MatchResult,
    evidence: tuple[Any, ...],
    *,
    params: _SignatureRuleParams,
    member_resolution: str,
    candidate_names: list[str],
    any_matching: bool,
) -> RuleResult:
    if any_matching:
        failure_reason = {
            "alias": "no_compatible_candidate_for_aliases",
            "regex": "no_compatible_candidate_for_pattern",
            "any": "no_compatible_candidate_for_any_name",
        }.get(params.name_match, "no_compatible_candidate")
        failure_message = _flexible_match_reason(
            name_match=params.name_match,
            source_name=source.name,
            aliases=params.aliases,
            pattern=params.pattern,
        )
    elif params.allow_missing:
        return _skip_optional_required_method(
            rule,
            source,
            anchor,
            match,
            evidence,
            mode=params.mode,
            declared_only=params.declared_only,
            member_resolution=member_resolution,
            member_origin="missing",
            details_extra=_flexible_details(
                params,
                candidate_names=candidate_names,
                resolved_candidate=None,
                ambiguity=None,
                failure_reason="optional_member_absent",
            ),
        )
    else:
        failure_reason = "no_candidate_in_matched_class_context"
        failure_message = (
            "no candidate method matched within the matched target class context"
        )
    details = _method_failure_details(
        failure_message,
        params,
        member_resolution=member_resolution,
        member_origin="missing",
        flexible=_flexible_details(
            params,
            candidate_names=candidate_names,
            resolved_candidate=None,
            ambiguity=None,
            failure_reason=failure_reason,
        ),
    )
    return _failed_method_result(rule, source, anchor, match, evidence, details)


def _evaluate_required_method_flexible(
    rule: Rule,
    source: Entity,
    target: Entity,
    target_class: Entity | None,
    match: MatchResult,
    evidence: tuple[Any, ...],
    *,
    ctx: EvalContext,
    params: _SignatureRuleParams,
) -> RuleResult:
    anchor_target = target_class or target
    pool = _flexible_candidate_pool(
        target, target_class, ctx, declared_only=params.declared_only
    )
    matching_candidates = _filter_by_flexible_name(pool.candidate_pool, source, params)
    compatible = _compatible_flexible_candidates(
        source, matching_candidates, ctx=ctx, params=params
    )
    candidate_names = sorted({candidate.name for candidate in matching_candidates})

    if len(compatible) == 1:
        resolved_target = compatible[0]
        return _evaluate_required_method_against_candidate(
            rule,
            source,
            resolved_target,
            match,
            evidence,
            ctx=ctx,
            mode=params.mode,
            check_return=params.check_return,
            allow_missing=params.allow_missing,
            declared_only=params.declared_only,
            enforce_method_kind=params.enforce_method_kind,
            member_resolution=pool.member_resolution,
            member_origin=(
                resolved_member_origin(resolved_target, target_class, ctx)
                if target_class is not None
                else "declared"
            ),
            details_extra=_flexible_details(
                params,
                candidate_names=candidate_names,
                resolved_candidate=resolved_target.name,
                ambiguity=None,
            ),
        )

    if len(compatible) > 1:
        details = _method_failure_details(
            "multiple compatible candidates matched flexible name resolution",
            params,
            member_resolution=pool.member_resolution,
            member_origin="ambiguous",
            flexible=_flexible_details(
                params,
                candidate_names=candidate_names,
                resolved_candidate=None,
                ambiguity={
                    "compatible_candidates": [
                        candidate.name for candidate in compatible
                    ],
                },
                failure_reason="multiple_compatible_candidates",
            ),
        )
        return _failed_method_result(
            rule, source, anchor_target, match, evidence, details
        )

    if _only_inherited_flexible_match(
        source, pool, matching_candidates, target_class, params
    ):
        details = _method_failure_details(
            "method is inherited but not declared directly on target class",
            params,
            member_resolution=pool.member_resolution,
            member_origin="inherited",
            flexible=_flexible_details(
                params,
                candidate_names=[],
                resolved_candidate=None,
                ambiguity=None,
                failure_reason="no_candidate_in_matched_class_context",
            ),
        )
        return _failed_method_result(
            rule, source, anchor_target, match, evidence, details
        )

    return _flexible_no_compatible_result(
        rule,
        source,
        anchor_target,
        match,
        evidence,
        params=params,
        member_resolution=pool.member_resolution,
        candidate_names=candidate_names,
        any_matching=bool(matching_candidates),
    )


def _evaluate_required_method(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    evidence: tuple[Any, ...],
    *,
    ctx: EvalContext,
    params: _SignatureRuleParams,
) -> RuleResult | None:
    """``None`` hands the rule on to the plain signature comparison."""
    target_class = _resolve_required_method_class(source, target, ctx=ctx)
    if params.name_match == "exact":
        return _evaluate_required_method_exact(
            rule,
            source,
            target,
            target_class,
            match,
            evidence,
            ctx=ctx,
            params=params,
        )
    return _evaluate_required_method_flexible(
        rule,
        source,
        target,
        target_class,
        match,
        evidence,
        ctx=ctx,
        params=params,
    )


def _signature_param_errors(
    source: Entity,
    target: Entity,
    source_model: dict[str, Any],
    target_model: dict[str, Any],
    *,
    ctx: EvalContext,
    params: _SignatureRuleParams,
) -> list[str]:
    expected_params = _strip_method_receiver(source_model.get("params", []), source)
    found_params = _strip_method_receiver(target_model.get("params", []), target)
    if params.mode == "exact":
        errors = _exact_compare(
            expected_params,
            found_params,
            source=source,
            target=target,
            ctx=ctx,
        )
    else:
        errors = _compatible_compare(
            expected_params,
            found_params,
            allow_extra_params=params.allow_extra,
            allow_param_rename=params.allow_rename,
            source=source,
            target=target,
            ctx=ctx,
        )
    errors = list(errors)
    if bool(source_model.get("vararg")) and not bool(target_model.get("vararg")):
        errors.append("missing *args support required by reference")
    if bool(source_model.get("kwarg")) and not bool(target_model.get("kwarg")):
        errors.append("missing **kwargs support required by reference")
    return errors


def _evaluate_signature_rule(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    evidence: tuple[Any, ...],
    *,
    ctx: EvalContext,
    params: _SignatureRuleParams,
) -> RuleResult:
    source_model = _param_model(source)
    target_model = _param_model(target)
    errors: List[str] = []
    if not params.return_only:
        errors.extend(
            _signature_param_errors(
                source, target, source_model, target_model, ctx=ctx, params=params
            )
        )
    if params.check_return:
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
        "mode": params.mode,
        "return_only": params.return_only,
        "check_return": params.check_return,
    }
    return build_rule_result(
        rule,
        source,
        target,
        match,
        status,
        details,
        evidence,
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

        # Evidence is gathered before dispatch, whichever rule this is.
        rule_evidence = (
            get_ast_signature(ctx, source.canonical_id, "source"),
            get_ast_signature(ctx, target.canonical_id, "target"),
            get_ast_annotations(ctx, source.canonical_id, "source"),
            get_ast_annotations(ctx, target.canonical_id, "target"),
        )
        params = _SignatureRuleParams.from_rule(rule)

        if rule.name == "required_constructor":
            return _evaluate_required_constructor_rule(
                rule,
                source,
                target,
                match,
                ctx=ctx,
                mode=params.mode,
                rule_evidence=rule_evidence,
            )
        if rule.name == "required_factory":
            return _evaluate_required_factory_rule(
                rule,
                source,
                target,
                match,
                ctx=ctx,
                mode=params.mode,
                rule_evidence=rule_evidence,
                aliases=params.aliases,
                pattern=params.pattern,
            )
        if rule.name == "required_method":
            result = _evaluate_required_method(
                rule, source, target, match, rule_evidence, ctx=ctx, params=params
            )
            if result is not None:
                return result
        return _evaluate_signature_rule(
            rule, source, target, match, rule_evidence, ctx=ctx, params=params
        )


__all__ = ["ApiSignatureEvaluator"]
