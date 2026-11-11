from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult
from pythonarchtesting.protocols.attribute_introspection import (
    ResolvedAttribute,
    collect_attributes,
    member_category_priority,
)

from .annotation_compatibility import compare_annotation_text
from .messages import build_rule_result


def _skip_optional_attribute(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
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
        member_category_priority(member),
        0 if member.annotation is not None else 1,
        member.lineno,
    )


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


@dataclass(frozen=True)
class _AttributeParams:
    """The normalised parameters of one required-attribute rule.

    Parsing them once keeps the evaluator free of parameter handling and gives
    the report payload and the candidate filters one shared reading of them.
    """

    name: str
    storage: str
    annotation: str | None
    allow_property: bool
    require_writable: bool
    declared_only: bool
    allow_missing: bool
    descriptor_kinds: frozenset[str]
    include_dynamic_attributes: bool
    interpret_dataclass_fields: bool

    @classmethod
    def from_rule(cls, rule: Rule) -> _AttributeParams:
        """Read the parameters from a compiled rule, applying their defaults."""
        params = rule.params
        annotation = params.get("annotation")
        return cls(
            name=str(params.get("name", "")).strip(),
            storage=str(params.get("storage", "any")).lower(),
            annotation=str(annotation) if annotation is not None else None,
            allow_property=bool(params.get("allow_property", False)),
            require_writable=bool(params.get("require_writable", False)),
            declared_only=bool(params.get("declared_only", False)),
            allow_missing=bool(params.get("allow_missing", False)),
            descriptor_kinds=frozenset(
                str(kind).strip().lower()
                for kind in params.get("descriptor_kinds", ())
                if str(kind).strip()
            ),
            include_dynamic_attributes=bool(
                params.get("include_dynamic_attributes", False)
            ),
            interpret_dataclass_fields=bool(
                params.get("interpret_dataclass_fields", False)
            ),
        )

    def payload(self) -> dict[str, Any]:
        """Describe the requirement for the report, in its established key order."""
        return {
            "name": self.name,
            "annotation": self.annotation,
            "storage": self.storage,
            "allow_property": self.allow_property,
            "require_writable": self.require_writable,
            "declared_only": self.declared_only,
            "allow_missing": self.allow_missing,
            "descriptor_kinds": sorted(self.descriptor_kinds),
            "include_dynamic_attributes": self.include_dynamic_attributes,
            "interpret_dataclass_fields": self.interpret_dataclass_fields,
        }


def _select_candidates(
    members: list[ResolvedAttribute], params: _AttributeParams
) -> tuple[list[ResolvedAttribute], list[ResolvedAttribute], list[ResolvedAttribute]]:
    """Narrow the members of the required name in three steps.

    The intermediate lists are returned as well, because the failure
    classification names the step at which the last candidate dropped out.
    The accepted candidates come back sorted by preference.
    """
    all_candidates = members
    if params.declared_only:
        all_candidates = [m for m in all_candidates if not m.inherited]

    storage_candidates = [
        member for member in all_candidates if _storage_matches(member, params.storage)
    ]
    matching_candidates = [
        member
        for member in storage_candidates
        if _descriptor_matches(
            member,
            allow_property=params.allow_property,
            descriptor_kinds=set(params.descriptor_kinds),
        )
    ]
    matching_candidates.sort(
        key=lambda member: _candidate_priority(member, storage=params.storage)
    )
    return all_candidates, storage_candidates, matching_candidates


def _first_passing(
    candidates: list[ResolvedAttribute],
    params: _AttributeParams,
    *,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> tuple[ResolvedAttribute | None, tuple[str, str] | None]:
    """Return the first candidate meeting the annotation and writability checks.

    The requirement is existential, so the search stops at the first passing
    candidate.  When none passes, the failure of the first rejected candidate
    is returned as a reason and its matching code; the report has always
    described that candidate, and the code has to name the same check.
    """
    first_failure: tuple[str, str] | None = None
    for member in candidates:
        if params.annotation is not None:
            comparison = compare_annotation_text(
                expected=params.annotation,
                found=member.annotation,
                expected_entity=source,
                found_entity=target,
                ctx=ctx,
                variance="invariant",
            )
            if not comparison.compatible:
                if first_failure is None:
                    first_failure = (
                        f"attribute annotation mismatch: "
                        f"expected {comparison.expected}, found {comparison.found}",
                        "attribute_present_but_annotation_mismatch",
                    )
                continue

        if params.require_writable and not member.is_writable:
            if first_failure is None:
                first_failure = (
                    _read_only_message(member, name=params.name),
                    "attribute_present_but_read_only",
                )
            continue

        return member, first_failure
    return None, first_failure


def _classify_failure(
    params: _AttributeParams,
    all_candidates: list[ResolvedAttribute],
    storage_candidates: list[ResolvedAttribute],
    matching_candidates: list[ResolvedAttribute],
    first_failure: tuple[str, str] | None,
) -> tuple[str, str]:
    """Name why no candidate satisfied the requirement, as a reason and a code.

    The cascade follows the narrowing of ``_select_candidates``: nothing of
    that name, nothing of the required storage, nothing of an accepted kind,
    and finally candidates that failed the annotation or writability check.
    """
    name = params.name
    if not all_candidates:
        return f"missing required attribute '{name}'", "missing_attribute_or_property"
    if not storage_candidates:
        found_storage = ", ".join(sorted({member.storage for member in all_candidates}))
        return (
            f"attribute storage mismatch for '{name}': "
            f"required {params.storage}, found {found_storage}",
            "storage_mismatch",
        )
    if not matching_candidates:
        # Only a plain property can fail ``_descriptor_matches``:
        # ``collect_attributes`` returns a cached_property or classproperty
        # only when its kind is among ``descriptor_kinds``, and such a member
        # is then accepted.  So every storage candidate is a property, and
        # ``allow_property`` is off.
        return (
            f"property '{name}' found, but properties do not satisfy "
            "required_attribute",
            "property_present_but_not_allowed",
        )
    if params.require_writable and all(
        not member.is_writable for member in matching_candidates
    ):
        return (
            _read_only_message(matching_candidates[0], name=name),
            "attribute_present_but_read_only",
        )
    # Every candidate failed a check, so a first failure has been recorded.
    return cast(tuple[str, str], first_failure)


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
        """Check that the target class has an attribute meeting the requirement."""
        entities = ctx.target_index.all_sorted
        params = _AttributeParams.from_rule(rule)

        by_name = collect_attributes(
            target,
            entities,
            include_inherited=True,
            include_instance=True,
            include_class=True,
            include_properties=True,
            include_dynamic_attributes=params.include_dynamic_attributes,
            descriptor_kinds=set(params.descriptor_kinds),
            interpret_dataclass_fields=params.interpret_dataclass_fields,
        )
        all_candidates, storage_candidates, matching_candidates = _select_candidates(
            by_name.get(params.name, []), params
        )
        required_attribute_payload = params.payload()

        if not all_candidates and params.allow_missing:
            skip_details = {
                "reason": (
                    f"Optional attribute '{params.name}' is not present on target class"
                ),
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

        passing_candidate, first_failure = _first_passing(
            matching_candidates, params, source=source, target=target, ctx=ctx
        )
        candidate_payloads = [_attribute_payload(member) for member in all_candidates]

        if passing_candidate is not None:
            success_details: dict[str, Any] = {
                "reason": "attribute requirement satisfied",
                "required_attribute": required_attribute_payload,
                "matched_attribute": _attribute_payload(passing_candidate),
                "candidate_attributes": candidate_payloads,
            }
            return build_rule_result(
                rule, source, target, match, "OK", success_details, ()
            )

        reason, fail_code = _classify_failure(
            params,
            all_candidates,
            storage_candidates,
            matching_candidates,
            first_failure,
        )
        details: dict[str, Any] = {
            "reason": reason,
            "fail_code": fail_code,
            "required_attribute": required_attribute_payload,
            "matched_attribute": None,
            "candidate_attributes": candidate_payloads,
            "allow_missing": params.allow_missing,
        }
        return build_rule_result(rule, source, target, match, "FAILED", details, ())


__all__ = ["AttributeContractEvaluator"]
