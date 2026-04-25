from __future__ import annotations

from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.protocols.entity_lookup import ProtocolEntityLookup

from .messages import _build_rule_result


def _entity_payload(entity: Entity) -> dict[str, Any]:
    return {
        "entity_id": entity.canonical_id,
        "module_path": entity.module_path,
        "qualname": entity.qualname,
        "name": entity.name,
    }


def _matched_target_entity(
    source_entity_id: str,
    ctx: EvalContext,
) -> tuple[Entity | None, str]:
    match = ctx.matches.get(source_entity_id)
    if match is None:
        return None, "missing"
    if match.status != MatchStatus.MATCHED or not match.target_id:
        return None, match.status.value
    return ctx.target_by_id.get(match.target_id), match.status.value


def _target_direct_bases(
    entity: Entity,
    lookup: ProtocolEntityLookup,
) -> tuple[Entity, ...]:
    return lookup.resolved_bases(entity)


def _target_all_ancestors(
    entity: Entity,
    lookup: ProtocolEntityLookup,
    visited: set[str] | None = None,
) -> tuple[Entity, ...]:
    if visited is None:
        visited = set()

    ancestors: list[Entity] = []
    for base_entity in _target_direct_bases(entity, lookup):
        if base_entity.canonical_id in visited:
            continue
        visited.add(base_entity.canonical_id)
        ancestors.append(base_entity)
        ancestors.extend(_target_all_ancestors(base_entity, lookup, visited))
    return tuple(ancestors)


def _contains_entity(entities: tuple[Entity, ...], expected: Entity) -> bool:
    return any(entity.canonical_id == expected.canonical_id for entity in entities)


def _relationship_holds(
    *,
    target: Entity,
    expected_target_base: Entity,
    direct_bases: tuple[Entity, ...],
    all_ancestors: tuple[Entity, ...],
    relationship_mode: str,
    allow_self: bool,
    transitive: bool,
    negated: bool,
) -> tuple[bool, str]:
    self_matches_required_base = (
        target.canonical_id == expected_target_base.canonical_id
    )

    if relationship_mode == "exact_type":
        if self_matches_required_base:
            return True, "target exactly matches the required nominal base counterpart"
        return (
            False,
            "target is not exactly the matched counterpart of the required base",
        )

    if relationship_mode != "subclass":
        raise ValueError(f"Unsupported nominal relationship mode: {relationship_mode}")

    candidate_bases = all_ancestors if transitive else direct_bases
    relationship_label = "target ancestry" if transitive else "target direct bases"
    contains_required_base = _contains_entity(candidate_bases, expected_target_base)

    if self_matches_required_base and not allow_self:
        if negated:
            return False, "target exactly matches the forbidden base counterpart"
        return (
            False,
            "target exactly matches the required base counterpart; strict subclass required",
        )

    if negated:
        if contains_required_base:
            return (
                False,
                f"{relationship_label} contains the matched counterpart of the forbidden base",
            )
        return (
            True,
            f"{relationship_label} does not contain the matched counterpart of the forbidden base",
        )

    if contains_required_base:
        if transitive:
            return True, "required nominal base found in target ancestry"
        return True, "required nominal base found in target direct bases"

    return (
        False,
        f"{relationship_label} does not contain the matched counterpart of the required base "
        f"({expected_target_base.module_path}.{expected_target_base.qualname})",
    )


class NominalTypeRelationshipEvaluator:
    """Evaluator for nominal class inheritance rules."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        expected_source_base_id = str(rule.params.get("expected_source_base_id", ""))
        source_base = ctx.source_by_id.get(expected_source_base_id)
        if source_base is None:
            raise ValueError(
                "Expected source base entity not found for rule "
                f"{rule.rule_id}: {expected_source_base_id}"
            )

        expected_target_base, match_status = _matched_target_entity(
            expected_source_base_id, ctx
        )
        lookup = ProtocolEntityLookup.from_entities(ctx.target_index.all_sorted)
        relationship_mode = str(rule.params.get("relationship_mode", "subclass"))
        allow_self = bool(rule.params.get("allow_self", False))
        transitive = bool(rule.params.get("transitive", True))
        negated = bool(rule.params.get("negated", False))
        target_direct_bases = _target_direct_bases(target, lookup)
        target_ancestors = _target_all_ancestors(target, lookup)

        details = {
            "reason": "",
            "required_base": {
                "declared": str(rule.params.get("base", "")),
                "expected_source_base_id": expected_source_base_id,
                "expected_source_base_qualname": source_base.qualname,
                "expected_target_base_id": (
                    expected_target_base.canonical_id
                    if expected_target_base is not None
                    else None
                ),
            },
            "relationship_mode": relationship_mode,
            "target_direct_bases": [
                _entity_payload(base_entity) for base_entity in target_direct_bases
            ],
            "target_ancestors": [
                _entity_payload(ancestor) for ancestor in target_ancestors
            ],
            "negated": negated,
            "transitive": transitive,
            "self_matches_required_base": False,
            "match_status": match_status,
        }

        if expected_target_base is None:
            details["reason"] = (
                "required base counterpart is not available in target matching "
                f"(status={match_status})"
            )
            return _build_rule_result(
                rule, source, target, match, "FAILED", details, ()
            )

        details["self_matches_required_base"] = (
            target.canonical_id == expected_target_base.canonical_id
        )
        relationship_holds, reason = _relationship_holds(
            target=target,
            expected_target_base=expected_target_base,
            direct_bases=target_direct_bases,
            all_ancestors=target_ancestors,
            relationship_mode=relationship_mode,
            allow_self=allow_self,
            transitive=transitive,
            negated=negated,
        )
        details["reason"] = reason

        return _build_rule_result(
            rule,
            source,
            target,
            match,
            "OK" if relationship_holds else "FAILED",
            details,
            (),
        )


__all__ = ["NominalTypeRelationshipEvaluator"]
