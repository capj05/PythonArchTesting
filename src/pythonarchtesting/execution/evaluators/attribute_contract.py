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
    }


def _storage_matches(
    member: ResolvedAttribute, storage: str, *, allow_property: bool
) -> bool:
    if storage == "instance":
        return member.storage == "instance" or (allow_property and member.storage == "property")
    if storage == "class":
        return member.storage == "class"
    # storage == "any"
    if member.storage == "property":
        return allow_property
    return True


def _candidate_priority(
    member: ResolvedAttribute, *, storage: str
) -> tuple[int, int, int, int]:
    return (
        0 if storage in {"class", "instance"} and member.storage == storage else 1,
        0 if not member.inherited else 1,
        0 if member.annotation is not None else 1,
        member.lineno,
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

        by_name = collect_attributes(
            target,
            entities,
            include_inherited=True,
            include_instance=True,
            include_class=True,
            include_properties=True,
        )
        all_candidates = by_name.get(name, [])

        if declared_only:
            all_candidates = [m for m in all_candidates if not m.inherited]

        matching_candidates = [
            member
            for member in all_candidates
            if _storage_matches(member, storage, allow_property=allow_property)
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
        }

        # Existential evaluation: return OK at the first passing candidate.
        _read_only_msg = (
            f"property '{name}' is read-only (no setter); "
            "require_writable=True requires a setter"
        )
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
            if require_writable and member.storage == "property" and not member.is_writable:
                if last_fail_reason is None:
                    last_fail_reason = _read_only_msg
                continue

            # This candidate passes all checks
            passing_candidate = member
            break

        if passing_candidate is not None:
            details = {
                "reason": "attribute requirement satisfied",
                "required_attribute": required_attribute_payload,
                "matched_attribute": _attribute_payload(passing_candidate),
                "candidate_attributes": [
                    _attribute_payload(member) for member in all_candidates
                ],
            }
            return _build_rule_result(rule, source, target, match, "OK", details, ())

        # Build failure reason
        if not all_candidates:
            reason = f"missing required attribute '{name}'"
            fail_code = "missing_attribute_or_property"
        elif not matching_candidates:
            # There are candidates but none match storage
            has_property = any(m.storage == "property" for m in all_candidates)
            if has_property and not allow_property:
                reason = (
                    f"property '{name}' found, but properties do not satisfy "
                    "required_attribute"
                )
                fail_code = "property_present_but_not_allowed"
            else:
                found_storage = ", ".join(
                    sorted({member.storage for member in all_candidates})
                )
                reason = (
                    f"attribute storage mismatch for '{name}': "
                    f"required {storage}, found {found_storage}"
                )
                fail_code = "storage_mismatch"
        else:
            # matching_candidates exist but all failed checks
            # Distinguish annotation mismatch vs writable mismatch
            has_property_candidate = any(
                m.storage == "property" for m in matching_candidates
            )
            if (
                has_property_candidate
                and allow_property
                and require_writable
                and all(
                    m.storage == "property" and not m.is_writable
                    for m in matching_candidates
                )
            ):
                reason = _read_only_msg
                fail_code = "property_present_but_read_only"
            else:
                reason = last_fail_reason  # type: ignore[assignment]
                fail_code = "attribute_present_but_annotation_mismatch"

        details = {
            "reason": reason,
            "fail_code": fail_code,
            "required_attribute": required_attribute_payload,
            "matched_attribute": None,
            "candidate_attributes": [
                _attribute_payload(member) for member in all_candidates
            ],
        }
        return _build_rule_result(rule, source, target, match, "FAILED", details, ())


__all__ = ["AttributeContractEvaluator"]
