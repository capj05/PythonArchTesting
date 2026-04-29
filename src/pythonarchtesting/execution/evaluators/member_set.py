from __future__ import annotations

from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

from .member_set_resolution import (
    SelectedMember,
    collect_attribute_members,
    collect_constructor_members,
    collect_method_members,
    filter_members_by_name_match,
)
from .messages import _build_rule_result

_ALL_MEMBER_KINDS = ("method", "attribute", "property", "descriptor", "constructor")


def _expand_requested_kinds(raw_kinds: list[str]) -> set[str]:
    if "any" in raw_kinds:
        return set(_ALL_MEMBER_KINDS)
    return set(raw_kinds)


def _member_payload(member: SelectedMember) -> dict[str, Any]:
    return {
        "name": member.name,
        "member_kind": member.member_kind,
        "qualname": member.qualname,
        "module_path": member.module_path,
        "lineno": member.lineno,
        "origin": member.origin,
        "inherited": member.inherited,
        "storage": member.storage,
        "method_kind": member.method_kind,
        "annotation": member.annotation,
        "descriptor_kind": member.descriptor_kind,
    }


def _failure_reason(
    *,
    count: int,
    min_count: int,
    max_count: int | None,
) -> str:
    if count == 0 and min_count > 0:
        return "no_matching_members_found"
    if count < min_count:
        return "too_few_matching_members"
    if max_count is not None and count > max_count:
        return "too_many_matching_members"
    return "matching_member_set_within_bounds"


def _reason_text(
    *,
    failure_reason: str,
    count: int,
    min_count: int,
    max_count: int | None,
) -> str:
    if failure_reason == "no_matching_members_found":
        return "no matching members found on the target class"
    if failure_reason == "too_few_matching_members":
        return (
            f"too few matching members found on the target class "
            f"(found {count}, required at least {min_count})"
        )
    if failure_reason == "too_many_matching_members":
        return (
            f"too many matching members found on the target class "
            f"(found {count}, allowed at most {max_count})"
        )
    if max_count is None:
        return (
            f"matching member set is within bounds "
            f"(found {count}, required at least {min_count})"
        )
    return (
        f"matching member set is within bounds "
        f"(found {count}, required between {min_count} and {max_count})"
    )


class MemberSetEvaluator:
    """Evaluator for generalized bulk member-selection rules (API006)."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        params = rule.params

        member_kinds_raw = params.get("member_kinds") or ["any"]
        if not isinstance(member_kinds_raw, list):
            member_kinds_raw = list(member_kinds_raw)
        member_kinds_lower = [str(kind).lower() for kind in member_kinds_raw]
        requested_kinds = _expand_requested_kinds(member_kinds_lower)

        name_match = str(params.get("name_match", "any")).lower()
        names = params.get("names")
        names_list = [str(name) for name in names] if isinstance(names, list) else None
        pattern_raw = params.get("pattern")
        pattern = (
            pattern_raw.strip() if isinstance(pattern_raw, str) and pattern_raw else None
        )
        declared_only = bool(params.get("declared_only", False))
        method_kind = str(params.get("method_kind", "any")).lower()
        storage = str(params.get("storage", "any")).lower()
        allow_property = bool(params.get("allow_property", True))
        descriptor_kinds_raw = params.get("descriptor_kinds")
        descriptor_kinds: tuple[str, ...] | None = (
            tuple(str(kind) for kind in descriptor_kinds_raw)
            if isinstance(descriptor_kinds_raw, list)
            else None
        )
        include_dynamic_attributes = bool(params.get("include_dynamic_attributes", False))
        interpret_dataclass_fields = bool(
            params.get("interpret_dataclass_fields", False)
        )
        constructor_kind = str(params.get("constructor_kind", "auto"))
        include_dataclass_constructor = bool(
            params.get("include_dataclass_constructor", True)
        )

        min_count = int(params.get("min_count", 1))
        max_count_value = params.get("max_count")
        max_count = int(max_count_value) if isinstance(max_count_value, int) else None

        common_details: dict[str, Any] = {
            "member_kinds": list(member_kinds_lower),
            "name_match": name_match,
            "names": names_list,
            "pattern": pattern,
            "declared_only": declared_only,
            "method_kind": method_kind,
            "storage": storage,
            "allow_property": allow_property,
            "descriptor_kinds": (
                list(descriptor_kinds) if descriptor_kinds is not None else None
            ),
            "include_dynamic_attributes": include_dynamic_attributes,
            "interpret_dataclass_fields": interpret_dataclass_fields,
            "constructor_kind": constructor_kind,
            "include_dataclass_constructor": include_dataclass_constructor,
            "min_count": min_count,
            "max_count": max_count,
        }

        if target.kind != "class":
            details = {
                "reason": (
                    f"matched target kind '{target.kind}' "
                    "does not support member-set checks"
                ),
                "failure_reason": "invalid_target_kind",
                "selected_count": 0,
                "selected_members": [],
                **common_details,
            }
            return _build_rule_result(rule, source, target, match, "FAILED", details, ())

        all_members: list[SelectedMember] = []

        if requested_kinds & {"method"}:
            all_members.extend(
                collect_method_members(
                    target,
                    ctx,
                    declared_only=declared_only,
                    method_kind=method_kind,
                )
            )

        attribute_kinds_requested = bool(
            requested_kinds & {"attribute", "property", "descriptor"}
        )
        if attribute_kinds_requested:
            effective_allow_property = allow_property and (
                "property" in requested_kinds or "any" in member_kinds_lower
            )
            effective_descriptor_kinds: tuple[str, ...] | None
            if "descriptor" in requested_kinds or "any" in member_kinds_lower:
                effective_descriptor_kinds = (
                    descriptor_kinds
                    if descriptor_kinds is not None
                    else ("cached_property", "classproperty")
                )
            else:
                effective_descriptor_kinds = None

            all_members.extend(
                collect_attribute_members(
                    target,
                    ctx,
                    declared_only=declared_only,
                    storage=storage,
                    allow_property=effective_allow_property,
                    descriptor_kinds=effective_descriptor_kinds,
                    include_dynamic_attributes=include_dynamic_attributes,
                    interpret_dataclass_fields=interpret_dataclass_fields,
                )
            )

        if requested_kinds & {"constructor"}:
            all_members.extend(
                collect_constructor_members(
                    target,
                    ctx,
                    declared_only=declared_only,
                    constructor_kind=constructor_kind,
                    include_dataclass_constructor=include_dataclass_constructor,
                )
            )

        kind_filtered = [
            member for member in all_members if member.member_kind in requested_kinds
        ]
        name_filtered = filter_members_by_name_match(
            kind_filtered,
            name_match=name_match,
            names=names_list,
            pattern=pattern,
        )

        selected = sorted(
            name_filtered,
            key=lambda m: (m.member_kind, m.name, m.qualname, m.lineno or 0),
        )
        selected_payload = [_member_payload(member) for member in selected]
        selected_count = len(selected)

        failure_reason = _failure_reason(
            count=selected_count,
            min_count=min_count,
            max_count=max_count,
        )
        status: RuleStatus = (
            "OK" if failure_reason == "matching_member_set_within_bounds" else "FAILED"
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
            "selected_members": selected_payload,
            **common_details,
        }
        return _build_rule_result(rule, source, target, match, status, details, ())


__all__ = ["MemberSetEvaluator"]
