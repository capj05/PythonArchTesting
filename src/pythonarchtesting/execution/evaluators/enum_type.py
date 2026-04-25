from __future__ import annotations

from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult
from pythonarchtesting.protocols.entity_lookup import ProtocolEntityLookup

from .messages import _build_rule_result

_STDLIB_ENUM_FAMILIES = frozenset(
    {
        "enum.Enum",
        "enum.IntEnum",
        "enum.StrEnum",
        "enum.Flag",
        "enum.IntFlag",
    }
)


def _target_bases(entity: Entity) -> list[str]:
    return [str(base) for base in entity.extras.get("bases") or []]


def _direct_stdlib_enum_family(base_refs: list[str]) -> str | None:
    for base_ref in base_refs:
        if base_ref in _STDLIB_ENUM_FAMILIES:
            return base_ref
    return None


def _classify_enum_like(
    entity: Entity,
    lookup: ProtocolEntityLookup,
    visited: set[str],
) -> tuple[bool, str | None, str | None, str]:
    if entity.canonical_id in visited:
        return False, None, None, "target_class_is_not_enum_like"
    visited.add(entity.canonical_id)

    base_refs = _target_bases(entity)
    direct_family = _direct_stdlib_enum_family(base_refs)
    if direct_family is not None:
        return (
            True,
            direct_family,
            "direct_stdlib_base",
            "recognized_direct_stdlib_enum_base",
        )

    for base_ref in base_refs:
        base_entity = lookup.unique_class_by_fqn(base_ref)
        if base_entity is None or base_entity.kind != "class":
            continue
        is_enum_like, enum_family, _, _ = _classify_enum_like(
            base_entity,
            lookup,
            visited,
        )
        if is_enum_like:
            return (
                True,
                enum_family,
                "transitive_local_enum_base",
                "recognized_transitive_enum_base",
            )

    return False, None, None, "target_class_is_not_enum_like"


class EnumTypeEvaluator:
    """Evaluator for enum classification rules."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        lookup = ProtocolEntityLookup.from_entities(ctx.target_index.all_sorted)
        target_bases = _target_bases(target)
        details: dict[str, Any] = {
            "reason": "",
            "enum_family": None,
            "target_bases": target_bases,
            "detection_origin": None,
        }

        if target.kind != "class":
            details["reason"] = "target_entity_is_not_class"
            return _build_rule_result(
                rule,
                source,
                target,
                match,
                "FAILED",
                details,
                (),
            )

        is_enum_like, enum_family, detection_origin, reason = _classify_enum_like(
            target,
            lookup,
            set(),
        )
        details["reason"] = reason
        details["enum_family"] = enum_family
        details["detection_origin"] = detection_origin

        return _build_rule_result(
            rule,
            source,
            target,
            match,
            "OK" if is_enum_like else "FAILED",
            details,
            (),
        )


__all__ = ["EnumTypeEvaluator"]
