from __future__ import annotations

from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

from .member_name_resolution import (
    filter_methods_by_name_match,
    member_origin,
    target_methods_for_class,
)
from .messages import _build_rule_result
from .signature_comparison import method_kind as resolved_method_kind


def _matches_method_kind(method: Entity, *, expected_kind: str) -> bool:
    if expected_kind == "any":
        return True
    actual_kind = resolved_method_kind(method)
    if expected_kind == "classmethod":
        return actual_kind == "class"
    if expected_kind == "staticmethod":
        return actual_kind == "static"
    return actual_kind == "instance"


def _method_payload(
    method: Entity, *, target: Entity, ctx: EvalContext
) -> dict[str, Any]:
    return {
        "module_path": method.module_path,
        "qualname": method.qualname,
        "name": method.name,
        "origin": member_origin(method, target, ctx),
        "method_kind": resolved_method_kind(method),
        "lineno": method.lineno,
    }


def _failure_reason(
    *,
    count: int,
    min_count: int,
    max_count: int | None,
) -> str:
    if count == 0 and min_count > 0:
        return "no_matching_methods_found"
    if count < min_count:
        return "too_few_matching_methods"
    if max_count is not None and count > max_count:
        return "too_many_matching_methods"
    return "matching_method_set_within_bounds"


def _reason_text(
    *,
    failure_reason: str,
    count: int,
    min_count: int,
    max_count: int | None,
) -> str:
    if failure_reason == "no_matching_methods_found":
        return "no matching methods found on the target class"
    if failure_reason == "too_few_matching_methods":
        return (
            f"too few matching methods found on the target class "
            f"(found {count}, required at least {min_count})"
        )
    if failure_reason == "too_many_matching_methods":
        return (
            f"too many matching methods found on the target class "
            f"(found {count}, allowed at most {max_count})"
        )
    if max_count is None:
        return (
            f"matching method set is within bounds "
            f"(found {count}, required at least {min_count})"
        )
    return (
        f"matching method set is within bounds "
        f"(found {count}, required between {min_count} and {max_count})"
    )


class MethodSetEvaluator:
    """Evaluator for bulk method-selection rules."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        name_match = str(rule.params.get("name_match", "any")).lower()
        names = rule.params.get("names")
        names_list = [str(name) for name in names] if isinstance(names, list) else None
        pattern = (
            str(rule.params.get("pattern")).strip()
            if isinstance(rule.params.get("pattern"), str)
            else None
        )
        declared_only = bool(rule.params.get("declared_only", False))
        method_kind = str(rule.params.get("method_kind", "any")).lower()
        min_count = int(rule.params.get("min_count", 1))
        max_count_value = rule.params.get("max_count")
        max_count = int(max_count_value) if isinstance(max_count_value, int) else None

        if target.kind != "class":
            details = {
                "reason": (
                    f"matched target kind '{target.kind}' "
                    "does not support method-set checks"
                ),
                "failure_reason": "invalid_target_kind",
                "selected_count": 0,
                "min_count": min_count,
                "max_count": max_count,
                "name_match": name_match,
                "names": names_list,
                "pattern": pattern,
                "declared_only": declared_only,
                "method_kind": method_kind,
                "selected_methods": [],
            }
            return _build_rule_result(
                rule,
                source,
                target,
                match,
                "FAILED",
                details,
                (),
            )

        candidate_methods = target_methods_for_class(
            target,
            ctx,
            include_inherited=not declared_only,
        )
        name_matched_methods = filter_methods_by_name_match(
            candidate_methods,
            source_name=None,
            name_match=name_match,
            aliases=None,
            pattern=pattern,
            names=names_list,
        )
        selected_methods = [
            method
            for method in name_matched_methods
            if _matches_method_kind(method, expected_kind=method_kind)
        ]
        selected_methods = sorted(
            selected_methods,
            key=lambda method: (method.name, method.qualname, method.lineno),
        )

        selected_payload = [
            _method_payload(method, target=target, ctx=ctx)
            for method in selected_methods
        ]
        selected_count = len(selected_methods)
        failure_reason = _failure_reason(
            count=selected_count,
            min_count=min_count,
            max_count=max_count,
        )
        status: RuleStatus = (
            "OK" if failure_reason == "matching_method_set_within_bounds" else "FAILED"
        )

        details = {
            "reason": _reason_text(
                failure_reason=failure_reason,
                count=selected_count,
                min_count=min_count,
                max_count=max_count,
            ),
            "failure_reason": failure_reason,
            "selected_count": selected_count,
            "min_count": min_count,
            "max_count": max_count,
            "name_match": name_match,
            "names": names_list,
            "pattern": pattern,
            "declared_only": declared_only,
            "method_kind": method_kind,
            "selected_methods": selected_payload,
        }
        return _build_rule_result(
            rule,
            source,
            target,
            match,
            status,
            details,
            (),
        )


__all__ = ["MethodSetEvaluator"]
