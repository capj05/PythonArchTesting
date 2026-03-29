"""
Rule evaluation logic extracted from rules.py.

This module contains the business logic for evaluating rules against entities,
with explicit inputs and outputs for testability.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.config import Config
from src.entities import Entity, EntityIndex
from src.matching import MatchResult, MatchStatus


def evaluate_rule(
    rule: Any,
    source_entity: Entity,
    match: MatchResult,
    ctx: Any,  # EvalContext
) -> Any:  # RuleResult
    """
    Evaluate a single rule against a match.

    Args:
        rule: Rule to evaluate
        source_entity: Source entity
        match: Match result
        ctx: Evaluation context

    Returns:
        RuleResult from evaluation
    """
    from src.core.models import RuleResult

    if not rule.enabled:
        return RuleResult(
            rule_id=rule.rule_id,
            status="SKIPPED",
            source_entity_id=source_entity.canonical_id,
            target_entity_id=match.target_id,
            match_status=match.status.value,
            confidence=match.confidence,
            message="Rule disabled.",
            evidence=(),
            details={"skipped": True, "reason": "disabled"},
        )

    if match.status != MatchStatus.MATCHED:
        if rule.rule_type == "import_policy":
            from src.execution.evaluators import get_rule_evaluator

            evaluator = get_rule_evaluator(rule.rule_type)
            if evaluator is None:
                return RuleResult(
                    rule_id=rule.rule_id,
                    status="ERROR",
                    source_entity_id=source_entity.canonical_id,
                    target_entity_id=match.target_id,
                    match_status=match.status.value,
                    confidence=match.confidence,
                    message="Unsupported rule type.",
                    evidence=(),
                    details={"rule_id": rule.rule_id},
                )

            fallback_target = (
                ctx.target_by_id.get(match.target_id)
                if match.target_id
                else (
                    ctx.target_index.all_sorted[0]
                    if getattr(ctx.target_index, "all_sorted", None)
                    else source_entity
                )
            )
            return evaluator.evaluate(rule, source_entity, fallback_target, match, ctx)

        if bool(rule.params.get("fail_on_unmatched", False)):
            return RuleResult(
                rule_id=rule.rule_id,
                status="FAILED",
                source_entity_id=source_entity.canonical_id,
                target_entity_id=match.target_id,
                match_status=match.status.value,
                confidence=match.confidence,
                message=("Required target entity missing or not matchable " f"(status={
                        match.status.value}, confidence={
                        match.confidence})."),
                evidence=(),
                details={
                    "reason": "required_target_missing",
                    "match_status": match.status.value,
                    "confidence": match.confidence,
                },
            )
        return RuleResult(
            rule_id=rule.rule_id,
            status="SKIPPED",
            source_entity_id=source_entity.canonical_id,
            target_entity_id=match.target_id,
            match_status=match.status.value,
            confidence=match.confidence,
            message=(
                "Rule skipped due to matching status "
                f"{match.status.value} (confidence={match.confidence})."
            ),
            evidence=(),
            details={
                "skipped": True,
                "reason": "match_status",
                "match_status": match.status.value,
            },
        )

    target_entity = ctx.target_by_id.get(match.target_id) if match.target_id else None
    if target_entity is None:
        return RuleResult(
            rule_id=rule.rule_id,
            status="ERROR",
            source_entity_id=source_entity.canonical_id,
            target_entity_id=match.target_id,
            match_status=match.status.value,
            confidence=match.confidence,
            message="Matched entity not found in target index.",
            evidence=(),
            details={"rule_id": rule.rule_id},
        )

    from src.execution.evaluators import get_rule_evaluator

    evaluator = get_rule_evaluator(rule.rule_type)
    if evaluator is None:
        return RuleResult(
            rule_id=rule.rule_id,
            status="ERROR",
            source_entity_id=source_entity.canonical_id,
            target_entity_id=target_entity.canonical_id,
            match_status=match.status.value,
            confidence=match.confidence,
            message="Unsupported rule type.",
            evidence=(),
            details={"rule_id": rule.rule_id},
        )

    return evaluator.evaluate(rule, source_entity, target_entity, match, ctx)


def evaluate_rules_for_target(
    *,
    rules: List[Any],
    source_index: EntityIndex,
    target_index: EntityIndex,
    matches: Dict[str, MatchResult],
    config: Config,
    source_by_id: Dict[str, Entity] | None = None,
    target_by_id: Dict[str, Entity] | None = None,
) -> Tuple[List[Any], List[Dict[str, Any]]]:
    """
    Evaluate all rules for a target.

    Args:
        rules: List of rules to evaluate
        source_index: Source entity index
        target_index: Target entity index
        matches: Match results
        config: Configuration object
        source_by_id: Optional pre-built source entity lookup
        target_by_id: Optional pre-built target entity lookup

    Returns:
        Tuple of (rule_results, errors)
    """
    from src.core.models import EvalContext

    ctx = EvalContext(
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=config,
        source_by_id=source_by_id or {},
        target_by_id=target_by_id or {},
    )
    rule_results: List[Any] = []
    errors: List[Dict[str, Any]] = []

    for rule in rules:
        if not rule.enabled:
            continue
        source_entity = ctx.source_by_id.get(rule.selector.source_entity_id)
        match = matches.get(rule.selector.source_entity_id)
        if source_entity is None or match is None:
            continue
        try:
            result = evaluate_rule(rule, source_entity, match, ctx)
            rule_results.append(result)
        except Exception as e:
            # Capture evaluation errors
            from src.core.models import RuleResult

            error_result = RuleResult(
                rule_id=rule.rule_id,
                status="ERROR",
                source_entity_id=source_entity.canonical_id,
                target_entity_id=match.target_id,
                match_status=match.status.value,
                confidence=match.confidence,
                message=f"Evaluation error: {str(e)}",
                evidence=(),
                details={"error": str(e), "rule_id": rule.rule_id},
            )
            rule_results.append(error_result)
            errors.append(
                {
                    "rule_id": rule.rule_id,
                    "error": str(e),
                    "source_entity": source_entity.canonical_id,
                }
            )

    return rule_results, errors


__all__ = [
    "evaluate_rule",
    "evaluate_rules_for_target",
]
