from __future__ import annotations

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


@dataclass(frozen=True)
class ForbiddenMemberHit:
    name: str
    member_kind: str
    storage: str | None
    lineno: int
    declared_on_qualname: str
    inherited: bool


def _enclosing_class_qualname(entity: Entity) -> str:
    if entity.kind != "method" or "." not in entity.qualname:
        return entity.qualname
    return entity.qualname.rsplit(".", 1)[0]


def _method_hit(member: Entity, *, target: Entity) -> ForbiddenMemberHit:
    declared_on_qualname = _enclosing_class_qualname(member)
    return ForbiddenMemberHit(
        name=member.name,
        member_kind="method",
        storage=None,
        lineno=member.lineno,
        declared_on_qualname=declared_on_qualname,
        inherited=declared_on_qualname != target.qualname,
    )


def _attribute_hit(member: Any) -> ForbiddenMemberHit:
    storage = str(getattr(member, "storage", "") or "")
    member_kind = "property" if storage == "property" else "attribute"
    return ForbiddenMemberHit(
        name=str(getattr(member, "name", "")),
        member_kind=member_kind,
        storage=storage or None,
        lineno=int(getattr(member, "lineno", 0) or 0),
        declared_on_qualname=str(getattr(member, "declared_on_qualname", "") or ""),
        inherited=bool(getattr(member, "inherited", False)),
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
    return {
        "name": hit.name,
        "member_kind": hit.member_kind,
        "storage": hit.storage,
        "lineno": hit.lineno,
        "declared_on_qualname": hit.declared_on_qualname,
        "inherited": hit.inherited,
    }


def _reason(name: str, hits: list[ForbiddenMemberHit]) -> str:
    first = hits[0]
    inherited = " inherited" if first.inherited else ""
    if first.member_kind == "attribute" and first.storage:
        return f"forbidden{inherited} {first.storage} attribute '{name}' is present"
    return f"forbidden{inherited} {first.member_kind} '{name}' is present"


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
        name = str(rule.params.get("name", "")).strip()
        member_kind = str(rule.params.get("member_kind", "any")).lower()
        storage = str(rule.params.get("storage", "any")).lower()
        declared_only = bool(rule.params.get("declared_only", False))

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
            }
            return _build_rule_result(
                rule, source, target, match, "FAILED", invalid_target_details, ()
            )

        hits: list[ForbiddenMemberHit] = []
        entities = ctx.target_index.all_sorted

        if member_kind in {"any", "method"}:
            methods = (
                declared_class_methods(target, entities)
                if declared_only
                else class_methods(target, entities)
            )
            hits.extend(
                _method_hit(member, target=target)
                for member in methods
                if member.name == name
            )

        if member_kind in {"any", "attribute", "property"}:
            attribute_members = collect_attributes(
                target,
                entities,
                include_inherited=not declared_only,
                include_instance=True,
                include_class=True,
                include_properties=True,
            ).get(name, [])
            for member in attribute_members:
                hit = _attribute_hit(member)
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
            "reason": ("forbidden member absent" if not hits else _reason(name, hits)),
            "forbidden_member": {
                "name": name,
                "member_kind": member_kind,
                "storage": storage,
                "declared_only": declared_only,
            },
            "hits": [_hit_payload(hit) for hit in hits],
            "match_status": match.status.value,
        }
        status: RuleStatus = "OK" if not hits else "FAILED"
        return _build_rule_result(rule, source, target, match, status, details, ())


__all__ = ["ForbiddenMemberHit", "MemberAbsenceEvaluator"]
