from __future__ import annotations

from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult

from .messages import _build_rule_result


class CompilerInvalidParamEvaluator:
    """Sentinel evaluator: surfaces compile-time invalid-param drops as FAILED.

    A `compiler_invalid_param` rule is synthesized by a decorator compiler
    when an invalid parameter value caused the real rule to be dropped.
    Without this sentinel the dropped rule would be invisible in
    ``status_counts`` even though compiler evidence was emitted.
    """

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        details: dict[str, Any] = {
            "reason": "compiler_invalid_param",
            "decorator": rule.params.get("decorator"),
            "param": rule.params.get("param"),
            "value": rule.params.get("value"),
            "valid": rule.params.get("valid"),
            "compiler_reason": rule.params.get("compiler_reason"),
        }
        return _build_rule_result(rule, source, target, match, "FAILED", details, ())


__all__ = ["CompilerInvalidParamEvaluator"]
