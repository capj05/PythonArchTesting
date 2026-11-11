from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult
from pythonarchtesting.protocols.attribute_introspection import collect_attributes
from pythonarchtesting.protocols.introspection import (
    class_methods,
    declared_class_methods,
)

from .messages import build_rule_result
from .signature_comparison import evaluate_method_compatibility


@dataclass(frozen=True)
class ForbiddenMemberHit:
    name: str
    member_kind: str
    storage: str | None
    lineno: int
    declared_on_qualname: str
    inherited: bool
    matched_name: str
    matched_via: str
    origin: str | None = None


def _enclosing_class_qualname(entity: Entity) -> str:
    if entity.kind != "method" or "." not in entity.qualname:
        return entity.qualname
    return entity.qualname.rsplit(".", 1)[0]


def _method_hit(
    member: Entity,
    *,
    target: Entity,
    matched_via: str,
) -> ForbiddenMemberHit:
    declared_on_qualname = _enclosing_class_qualname(member)
    return ForbiddenMemberHit(
        name=member.name,
        member_kind="method",
        storage=None,
        lineno=member.lineno,
        declared_on_qualname=declared_on_qualname,
        inherited=declared_on_qualname != target.qualname,
        matched_name=member.name,
        matched_via=matched_via,
    )


def _attribute_hit(member: Any, *, matched_via: str) -> ForbiddenMemberHit:
    storage = str(getattr(member, "storage", "") or "")
    member_kind = "property" if storage == "property" else "attribute"
    return ForbiddenMemberHit(
        name=str(getattr(member, "name", "")),
        member_kind=member_kind,
        storage=storage or None,
        lineno=int(getattr(member, "lineno", 0) or 0),
        declared_on_qualname=str(getattr(member, "declared_on_qualname", "") or ""),
        inherited=bool(getattr(member, "inherited", False)),
        matched_name=str(getattr(member, "name", "")),
        matched_via=matched_via,
        origin=str(getattr(member, "origin", "") or "") or None,
    )


def _storage_matches(storage: str, member_storage: str | None) -> bool:
    if storage == "any":
        return True
    return member_storage == storage


def _hit_sort_key(hit: ForbiddenMemberHit) -> tuple[int, int, str, str]:
    return (
        0 if not hit.inherited else 1,
        hit.lineno,
        hit.member_kind,
        hit.declared_on_qualname,
    )


def _hit_payload(hit: ForbiddenMemberHit) -> dict[str, Any]:
    payload = {
        "name": hit.name,
        "member_kind": hit.member_kind,
        "storage": hit.storage,
        "lineno": hit.lineno,
        "declared_on_qualname": hit.declared_on_qualname,
        "inherited": hit.inherited,
        "matched_name": hit.matched_name,
        "matched_via": hit.matched_via,
    }
    if hit.origin is not None:
        payload["origin"] = hit.origin
    return payload


def _reason(hits: list[ForbiddenMemberHit]) -> str:
    first = hits[0]
    inherited = " inherited" if first.inherited else ""
    if first.member_kind == "attribute" and first.storage:
        return (
            f"forbidden{inherited} {first.storage} attribute "
            f"'{first.matched_name}' is present"
        )
    return f"forbidden{inherited} {first.member_kind} '{first.matched_name}' is present"


def _name_matches(
    candidate_name: str,
    *,
    rule_name: str | None,
    name_match: str,
    aliases: list[str] | None,
    pattern: str | None,
) -> tuple[bool, str | None]:
    if name_match == "regex":
        if pattern is None:
            return False, None
        return (re.fullmatch(pattern, candidate_name) is not None), "regex"
    if name_match == "alias":
        if not aliases:
            return False, None
        return candidate_name in aliases, "alias"
    if rule_name is None:
        return False, None
    return candidate_name == rule_name, "exact"


def _resolve_signature_anchor(rule: Rule, ctx: EvalContext) -> Entity | None:
    anchor_id = rule.params.get("signature_anchor_entity_id")
    if not isinstance(anchor_id, str) or not anchor_id:
        return None
    anchor = ctx.source_by_id.get(anchor_id)
    if isinstance(anchor, Entity) and anchor.kind == "method":
        return anchor
    return None


@dataclass(frozen=True)
class _AbsenceParams:
    """The normalised parameters of one forbidden-member rule.

    ``aliases`` and ``pattern`` stay ``None`` when the rule does not carry them
    in the expected type, which also decides whether the report lists them.
    """

    name: str | None
    member_kind: str
    storage: str
    declared_only: bool
    name_match: str
    aliases: list[str] | None
    pattern: str | None
    signature_mode: str
    include_descriptors: bool
    include_dynamic_attributes: bool

    @classmethod
    def from_rule(cls, rule: Rule) -> _AbsenceParams:
        """Read the parameters from a compiled rule, applying their defaults."""
        params = rule.params
        name_raw = params.get("name")
        aliases_raw = params.get("aliases")
        pattern_raw = params.get("pattern")
        return cls(
            name=str(name_raw).strip() if isinstance(name_raw, str) else None,
            member_kind=str(params.get("member_kind", "any")).lower(),
            storage=str(params.get("storage", "any")).lower(),
            declared_only=bool(params.get("declared_only", False)),
            name_match=str(params.get("name_match", "exact")).lower(),
            aliases=(
                [str(alias) for alias in aliases_raw]
                if isinstance(aliases_raw, list)
                else None
            ),
            # Stripped as in ``api_signature``; the compiler checks it stripped.
            pattern=pattern_raw.strip() if isinstance(pattern_raw, str) else None,
            signature_mode=str(params.get("signature_mode", "any")).lower(),
            include_descriptors=bool(params.get("include_descriptors", False)),
            include_dynamic_attributes=bool(
                params.get("include_dynamic_attributes", False)
            ),
        )

    def name_matches(self, candidate_name: str) -> tuple[bool, str | None]:
        """Match a member name under the rule's naming mode."""
        return _name_matches(
            candidate_name,
            rule_name=self.name,
            name_match=self.name_match,
            aliases=self.aliases,
            pattern=self.pattern,
        )


def _base_details(
    params: _AbsenceParams,
    match: MatchResult,
    *,
    reason: str,
    hits: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the details every result shares, in their established key order.

    The early failures stop here; only the final result appends ``aliases``
    and ``pattern``, so their position at the end is part of the report shape.
    """
    return {
        "reason": reason,
        "forbidden_member": {
            "name": params.name,
            "member_kind": params.member_kind,
            "storage": params.storage,
            "declared_only": params.declared_only,
        },
        "hits": hits,
        "match_status": match.status.value,
        "name_match": params.name_match,
        "signature_mode": params.signature_mode,
    }


def _method_hits(
    params: _AbsenceParams,
    target: Entity,
    entities: Any,
    *,
    signature_anchor: Entity | None,
    ctx: EvalContext,
) -> list[ForbiddenMemberHit]:
    """Return the target's methods matching the forbidden name.

    With a signature anchor a method only counts when its signature is also
    compatible with the anchor's, so a same-named method of another shape
    is allowed.
    """
    methods = (
        declared_class_methods(target, entities)
        if params.declared_only
        else class_methods(target, entities)
    )
    hits: list[ForbiddenMemberHit] = []
    for member in methods:
        matched, matched_via = params.name_matches(member.name)
        if not matched or matched_via is None:
            continue
        if signature_anchor is not None:
            comparison = evaluate_method_compatibility(
                signature_anchor,
                member,
                ctx=ctx,
                mode=params.signature_mode,
                enforce_method_kind=True,
                check_return=False,
            )
            if comparison["errors"]:
                continue
        hits.append(_method_hit(member, target=target, matched_via=matched_via))
    return hits


def _accepts(hit: ForbiddenMemberHit, member_kind: str, storage: str) -> bool:
    """Tell whether an attribute hit is of the forbidden kind and storage.

    The storage filter applies to plain attributes only; a property has no
    storage to compare.
    """
    if member_kind == "attribute" and hit.member_kind != "attribute":
        return False
    if member_kind == "property" and hit.member_kind != "property":
        return False
    return hit.member_kind != "attribute" or _storage_matches(storage, hit.storage)


def _attribute_hits(
    params: _AbsenceParams, target: Entity, entities: Any
) -> list[ForbiddenMemberHit]:
    """Return the target's attributes and properties matching the forbidden name."""
    attribute_members = collect_attributes(
        target,
        entities,
        include_inherited=not params.declared_only,
        include_instance=True,
        include_class=True,
        include_properties=True,
        include_descriptors=params.include_descriptors,
        include_dynamic_attributes=params.include_dynamic_attributes,
    )
    hits: list[ForbiddenMemberHit] = []
    for members in attribute_members.values():
        for attribute_member in members:
            matched, matched_via = params.name_matches(
                str(getattr(attribute_member, "name", ""))
            )
            if not matched or matched_via is None:
                continue
            hit = _attribute_hit(attribute_member, matched_via=matched_via)
            if _accepts(hit, params.member_kind, params.storage):
                hits.append(hit)
    return hits


def _collect_hits(
    params: _AbsenceParams,
    target: Entity,
    entities: Any,
    *,
    signature_anchor: Entity | None,
    ctx: EvalContext,
) -> list[ForbiddenMemberHit]:
    """Gather the forbidden members of the requested kinds, best hit first.

    Methods are collected before attributes; the stable sort keeps that order
    for hits whose sort keys tie.
    """
    hits: list[ForbiddenMemberHit] = []
    if params.member_kind in {"any", "method"}:
        hits.extend(
            _method_hits(
                params, target, entities, signature_anchor=signature_anchor, ctx=ctx
            )
        )
    if params.member_kind in {"any", "attribute", "property"}:
        hits.extend(_attribute_hits(params, target, entities))
    hits.sort(key=_hit_sort_key)
    return hits


def _final_details(
    params: _AbsenceParams, match: MatchResult, hits: list[ForbiddenMemberHit]
) -> dict[str, Any]:
    """Build the details of a completed check, naming aliases and pattern last."""
    details = _base_details(
        params,
        match,
        reason="forbidden member absent" if not hits else _reason(hits),
        hits=[_hit_payload(hit) for hit in hits],
    )
    if params.aliases is not None:
        details["aliases"] = params.aliases
    if params.pattern is not None:
        details["pattern"] = params.pattern
    return details


class MemberAbsenceEvaluator:
    """Evaluator for forbidden class-member declarations."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        """Report every member of the target class that the rule forbids."""
        params = _AbsenceParams.from_rule(rule)

        if target.kind != "class":
            invalid_target_details = _base_details(
                params,
                match,
                reason=(
                    f"matched target kind '{target.kind}' "
                    "does not support member absence checks"
                ),
                hits=[],
            )
            return build_rule_result(
                rule, source, target, match, "FAILED", invalid_target_details, ()
            )

        needs_anchor = params.signature_mode in {"compatible", "exact"}
        signature_anchor = (
            _resolve_signature_anchor(rule, ctx) if needs_anchor else None
        )
        if needs_anchor and signature_anchor is None:
            missing_anchor_details = _base_details(
                params,
                match,
                reason="missing source signature anchor for forbidden method check",
                hits=[],
            )
            return build_rule_result(
                rule, source, target, match, "FAILED", missing_anchor_details, ()
            )

        hits = _collect_hits(
            params,
            target,
            ctx.target_index.all_sorted,
            signature_anchor=signature_anchor,
            ctx=ctx,
        )
        details = _final_details(params, match, hits)
        status: RuleStatus = "OK" if not hits else "FAILED"
        return build_rule_result(rule, source, target, match, status, details, ())


__all__ = ["ForbiddenMemberHit", "MemberAbsenceEvaluator"]
