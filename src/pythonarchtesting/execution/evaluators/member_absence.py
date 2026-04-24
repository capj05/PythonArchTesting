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

from .messages import _build_rule_result
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
        name_raw = rule.params.get("name")
        name = str(name_raw).strip() if isinstance(name_raw, str) else None
        member_kind = str(rule.params.get("member_kind", "any")).lower()
        storage = str(rule.params.get("storage", "any")).lower()
        declared_only = bool(rule.params.get("declared_only", False))
        name_match = str(rule.params.get("name_match", "exact")).lower()
        aliases_raw = rule.params.get("aliases")
        aliases = (
            [str(alias) for alias in aliases_raw]
            if isinstance(aliases_raw, list)
            else None
        )
        pattern = (
            str(rule.params.get("pattern")).strip()
            if isinstance(rule.params.get("pattern"), str)
            else None
        )
        signature_mode = str(rule.params.get("signature_mode", "any")).lower()
        include_descriptors = bool(rule.params.get("include_descriptors", False))
        include_dynamic_attributes = bool(
            rule.params.get("include_dynamic_attributes", False)
        )

        if target.kind != "class":
            invalid_target_details: dict[str, Any] = {
                "reason": (
                    f"matched target kind '{target.kind}' "
                    "does not support member absence checks"
                ),
                "forbidden_member": {
                    "name": name,
                    "member_kind": member_kind,
                    "storage": storage,
                    "declared_only": declared_only,
                },
                "hits": [],
                "match_status": match.status.value,
                "name_match": name_match,
                "signature_mode": signature_mode,
            }
            return _build_rule_result(
                rule, source, target, match, "FAILED", invalid_target_details, ()
            )

        signature_anchor = (
            _resolve_signature_anchor(rule, ctx)
            if signature_mode in {"compatible", "exact"}
            else None
        )
        if signature_mode in {"compatible", "exact"} and signature_anchor is None:
            return _build_rule_result(
                rule,
                source,
                target,
                match,
                "FAILED",
                {
                    "reason": "missing source signature anchor for forbidden method check",
                    "forbidden_member": {
                        "name": name,
                        "member_kind": member_kind,
                        "storage": storage,
                        "declared_only": declared_only,
                    },
                    "hits": [],
                    "match_status": match.status.value,
                    "name_match": name_match,
                    "signature_mode": signature_mode,
                },
                (),
            )

        hits: list[ForbiddenMemberHit] = []
        entities = ctx.target_index.all_sorted

        if member_kind in {"any", "method"}:
            methods = (
                declared_class_methods(target, entities)
                if declared_only
                else class_methods(target, entities)
            )
            for member in methods:
                matched, matched_via = _name_matches(
                    member.name,
                    rule_name=name,
                    name_match=name_match,
                    aliases=aliases,
                    pattern=pattern,
                )
                if not matched or matched_via is None:
                    continue
                if signature_anchor is not None:
                    comparison = evaluate_method_compatibility(
                        signature_anchor,
                        member,
                        ctx=ctx,
                        mode=signature_mode,
                        enforce_method_kind=True,
                        check_return=False,
                    )
                    if comparison["errors"]:
                        continue
                hits.append(_method_hit(member, target=target, matched_via=matched_via))

        if member_kind in {"any", "attribute", "property"}:
            attribute_members = collect_attributes(
                target,
                entities,
                include_inherited=not declared_only,
                include_instance=True,
                include_class=True,
                include_properties=True,
                include_descriptors=include_descriptors,
                include_dynamic_attributes=include_dynamic_attributes,
            )
            for members in attribute_members.values():
                for attribute_member in members:
                    matched, matched_via = _name_matches(
                        str(getattr(attribute_member, "name", "")),
                        rule_name=name,
                        name_match=name_match,
                        aliases=aliases,
                        pattern=pattern,
                    )
                    if not matched or matched_via is None:
                        continue
                    hit = _attribute_hit(attribute_member, matched_via=matched_via)
                    if member_kind == "attribute" and hit.member_kind != "attribute":
                        continue
                    if member_kind == "property" and hit.member_kind != "property":
                        continue
                    if hit.member_kind == "attribute" and not _storage_matches(
                        storage, hit.storage
                    ):
                        continue
                    hits.append(hit)

        hits.sort(key=_hit_sort_key)
        details: dict[str, Any] = {
            "reason": ("forbidden member absent" if not hits else _reason(hits)),
            "forbidden_member": {
                "name": name,
                "member_kind": member_kind,
                "storage": storage,
                "declared_only": declared_only,
            },
            "hits": [_hit_payload(hit) for hit in hits],
            "match_status": match.status.value,
            "name_match": name_match,
            "signature_mode": signature_mode,
        }
        if aliases is not None:
            details["aliases"] = aliases
        if pattern is not None:
            details["pattern"] = pattern
        status: RuleStatus = "OK" if not hits else "FAILED"
        return _build_rule_result(rule, source, target, match, status, details, ())


__all__ = ["ForbiddenMemberHit", "MemberAbsenceEvaluator"]
