from __future__ import annotations

from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult
from pythonarchtesting.protocols.attribute_introspection import (
    ResolvedAttribute,
    collect_attributes,
)

from .annotation_compatibility import compare_annotation_text
from .messages import _build_rule_result


def _skip_optional_attribute(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
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
        (),
    )


def _attribute_payload(member: ResolvedAttribute) -> dict[str, Any]:
    return {
        "name": member.name,
        "annotation": member.annotation,
        "storage": member.storage,
        "lineno": member.lineno,
        "declared_on_qualname": member.declared_on_qualname,
        "inherited": member.inherited,
        "is_writable": member.is_writable,
        "origin": member.origin,
        "descriptor_kind": member.descriptor_kind,
    }


def _storage_matches(member: ResolvedAttribute, storage: str) -> bool:
    if storage == "instance":
        return member.storage in {"instance", "property"}
    if storage == "class":
        return member.storage == "class"
    return True


def _candidate_priority(
    member: ResolvedAttribute, *, storage: str
) -> tuple[int, int, int, int, int]:
    return (
        0 if storage in {"class", "instance"} and member.storage == storage else 1,
        0 if not member.inherited else 1,
        _member_category_priority(member),
        0 if member.annotation is not None else 1,
        member.lineno,
    )


def _member_category_priority(member: ResolvedAttribute) -> int:
    if member.origin in {"dynamic_setattr_instance", "dynamic_setattr_class"}:
        return 2
    if member.storage == "property" or member.descriptor_kind is not None:
        return 1
    return 0


def _descriptor_matches(
    member: ResolvedAttribute,
    *,
    allow_property: bool,
    descriptor_kinds: set[str],
) -> bool:
    if member.storage != "property" and member.descriptor_kind is None:
        return True
    if member.descriptor_kind is None:
        return allow_property
    return member.descriptor_kind in descriptor_kinds


def _descriptor_rejection(
    member: ResolvedAttribute,
    *,
    name: str,
) -> tuple[str, str]:
    if member.descriptor_kind == "cached_property":
        return (
            f"descriptor '{name}' found, but cached_property does not satisfy "
            "required_attribute without descriptor_kinds=('cached_property',)",
            "descriptor_present_but_not_enabled",
        )
    if member.descriptor_kind == "classproperty":
        return (
            f"descriptor '{name}' found, but classproperty does not satisfy "
            "required_attribute without descriptor_kinds=('classproperty',)",
            "descriptor_present_but_not_enabled",
        )
    return (
        f"property '{name}' found, but properties do not satisfy required_attribute",
        "property_present_but_not_allowed",
    )


def _read_only_message(member: ResolvedAttribute, *, name: str) -> str:
    if member.descriptor_kind == "cached_property":
        return (
            f"cached_property '{name}' is read-only; "
            "require_writable=True requires a writable attribute"
        )
    if member.descriptor_kind == "classproperty":
        return (
            f"classproperty '{name}' is read-only; "
            "require_writable=True requires a writable attribute"
        )
    return (
        f"property '{name}' is read-only (no setter); "
        "require_writable=True requires a setter"
    )


class AttributeContractEvaluator:
    """Evaluator for required class and instance attributes."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        entities = ctx.target_index.all_sorted
        name = str(rule.params.get("name", "")).strip()
        storage = str(rule.params.get("storage", "any")).lower()
        expected_annotation = rule.params.get("annotation")
        if expected_annotation is not None:
            expected_annotation = str(expected_annotation)

        allow_property = bool(rule.params.get("allow_property", False))
        require_writable = bool(rule.params.get("require_writable", False))
        declared_only = bool(rule.params.get("declared_only", False))
        allow_missing = bool(rule.params.get("allow_missing", False))
        descriptor_kinds = {
            str(kind).strip().lower()
            for kind in rule.params.get("descriptor_kinds", ())
            if str(kind).strip()
        }
        include_dynamic_attributes = bool(
            rule.params.get("include_dynamic_attributes", False)
        )
        interpret_dataclass_fields = bool(
            rule.params.get("interpret_dataclass_fields", False)
        )

        by_name = collect_attributes(
            target,
            entities,
            include_inherited=True,
            include_instance=True,
            include_class=True,
            include_properties=True,
            include_dynamic_attributes=include_dynamic_attributes,
            descriptor_kinds=descriptor_kinds,
            interpret_dataclass_fields=interpret_dataclass_fields,
        )
        all_candidates = by_name.get(name, [])

        if declared_only:
            all_candidates = [m for m in all_candidates if not m.inherited]

        storage_candidates = [
            member for member in all_candidates if _storage_matches(member, storage)
        ]
        matching_candidates = [
            member
            for member in storage_candidates
            if _descriptor_matches(
                member,
                allow_property=allow_property,
                descriptor_kinds=descriptor_kinds,
            )
        ]
        matching_candidates.sort(
            key=lambda member: _candidate_priority(member, storage=storage)
        )

        required_attribute_payload = {
            "name": name,
            "annotation": expected_annotation,
            "storage": storage,
            "allow_property": allow_property,
            "require_writable": require_writable,
            "declared_only": declared_only,
            "allow_missing": allow_missing,
            "descriptor_kinds": sorted(descriptor_kinds),
            "include_dynamic_attributes": include_dynamic_attributes,
            "interpret_dataclass_fields": interpret_dataclass_fields,
        }

        if not all_candidates and allow_missing:
            skip_details = {
                "reason": f"Optional attribute '{name}' is not present on target class",
                "failure_reason": "optional_member_absent",
                "allow_missing": True,
                "required_attribute": required_attribute_payload,
                "matched_attribute": None,
                "candidate_attributes": [],
            }
            return _skip_optional_attribute(
                rule,
                source,
                target,
                match,
                details=skip_details,
            )

        # Existential evaluation: return OK at the first passing candidate.
        last_fail_reason: str | None = None
        passing_candidate: ResolvedAttribute | None = None

        for member in matching_candidates:
            # Check annotation compatibility
            if expected_annotation is not None:
                comparison = compare_annotation_text(
                    expected=expected_annotation,
                    found=member.annotation,
                    expected_entity=source,
                    found_entity=target,
                    ctx=ctx,
                    variance="invariant",
                )
                if not comparison.compatible:
                    if last_fail_reason is None:
                        last_fail_reason = (
                            f"attribute annotation mismatch: "
                            f"expected {comparison.expected}, found {comparison.found}"
                        )
                    continue

            # Check require_writable (only meaningful for properties)
            if require_writable and not member.is_writable:
                if last_fail_reason is None:
                    last_fail_reason = _read_only_message(member, name=name)
                continue

            # This candidate passes all checks
            passing_candidate = member
            break

        if passing_candidate is not None:
            success_details: dict[str, Any] = {
                "reason": "attribute requirement satisfied",
                "required_attribute": required_attribute_payload,
                "matched_attribute": _attribute_payload(passing_candidate),
                "candidate_attributes": [
                    _attribute_payload(member) for member in all_candidates
                ],
            }
            return _build_rule_result(
                rule, source, target, match, "OK", success_details, ()
            )

        # Build failure reason
        if not all_candidates:
            reason = f"missing required attribute '{name}'"
            fail_code = "missing_attribute_or_property"
        elif not storage_candidates:
            found_storage = ", ".join(
                sorted({member.storage for member in all_candidates})
            )
            reason = (
                f"attribute storage mismatch for '{name}': "
                f"required {storage}, found {found_storage}"
            )
            fail_code = "storage_mismatch"
        elif not matching_candidates:
            best_descriptor_candidate = sorted(
                storage_candidates,
                key=lambda member: _candidate_priority(member, storage=storage),
            )[0]
            if not _descriptor_matches(
                best_descriptor_candidate,
                allow_property=allow_property,
                descriptor_kinds=descriptor_kinds,
            ):
                reason, fail_code = _descriptor_rejection(
                    best_descriptor_candidate,
                    name=name,
                )
            else:
                reason = last_fail_reason or f"missing required attribute '{name}'"
                fail_code = "attribute_present_but_not_accepted"
        else:
            # matching_candidates exist but all failed checks
            # Distinguish annotation mismatch vs writable mismatch
            if (
                require_writable
                and matching_candidates
                and all(not m.is_writable for m in matching_candidates)
            ):
                reason = _read_only_message(matching_candidates[0], name=name)
                fail_code = "attribute_present_but_read_only"
            else:
                reason = last_fail_reason  # type: ignore[assignment]
                fail_code = "attribute_present_but_annotation_mismatch"

        details: dict[str, Any] = {
            "reason": reason,
            "fail_code": fail_code,
            "required_attribute": required_attribute_payload,
            "matched_attribute": None,
            "candidate_attributes": [
                _attribute_payload(member) for member in all_candidates
            ],
            "allow_missing": allow_missing,
        }
        return _build_rule_result(rule, source, target, match, "FAILED", details, ())


__all__ = ["AttributeContractEvaluator"]
