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


def _target_ancestors(
    entity: Entity,
    lookup: ProtocolEntityLookup,
    visited: set[str] | None = None,
) -> tuple[Entity, ...]:
    if visited is None:
        visited = set()

    ancestors: list[Entity] = []
    for base_entity in lookup.resolved_bases(entity):
        if base_entity.canonical_id in visited:
            continue
        visited.add(base_entity.canonical_id)
        ancestors.append(base_entity)
        ancestors.extend(_target_ancestors(base_entity, lookup, visited))
    return tuple(ancestors)


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
        target_ancestors = _target_ancestors(target, lookup)

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
            "target_ancestors": [
                _entity_payload(ancestor) for ancestor in target_ancestors
            ],
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

        if any(
            ancestor.canonical_id == expected_target_base.canonical_id
            for ancestor in target_ancestors
        ):
            details["reason"] = "required nominal base found in target ancestry"
            return _build_rule_result(rule, source, target, match, "OK", details, ())

        details["reason"] = (
            "target ancestry does not contain the matched counterpart of the "
            f"required base ({expected_target_base.module_path}.{expected_target_base.qualname})"
        )
        return _build_rule_result(rule, source, target, match, "FAILED", details, ())


__all__ = ["NominalTypeRelationshipEvaluator"]
