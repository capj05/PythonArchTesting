from __future__ import annotations

from typing import Any, Dict

from .api_signature import ApiSignatureEvaluator
from .import_policy import ImportPolicyEvaluator
from .protocol_conformance import ProtocolConformanceEvaluator
from .variable_flow import VariableFlowEvaluator

# Registry of evaluators for different rule types.
_EVALUATORS: Dict[str, Any] = {
    "api_signature": ApiSignatureEvaluator(),
    "import_policy": ImportPolicyEvaluator(),
    "protocol_conformance": ProtocolConformanceEvaluator(),
    "variable_flow": VariableFlowEvaluator(),
}


def get_rule_evaluator(rule_type: str) -> Any:
    """
    Get the evaluator for a rule type.

    Args:
        rule_type: Type of rule

    Returns:
        Evaluator instance or None if not found
    """
    return _EVALUATORS.get(rule_type)


def register_rule_evaluator(rule_type: str, evaluator: Any) -> None:
    """
    Register a new rule evaluator.

    Args:
        rule_type: Rule type this evaluator handles
        evaluator: Evaluator instance
    """
    _EVALUATORS[rule_type] = evaluator


__all__ = ["get_rule_evaluator", "register_rule_evaluator"]
