from __future__ import annotations

from typing import Any, Dict

from .api_signature import ApiSignatureEvaluator
from .attribute_contract import AttributeContractEvaluator
from .enum_type import EnumTypeEvaluator
from .import_policy import ImportPolicyEvaluator
from .member_absence import MemberAbsenceEvaluator
from .method_set import MethodSetEvaluator
from .nominal_type_relationship import NominalTypeRelationshipEvaluator
from .protocol_conformance import ProtocolConformanceEvaluator
from .python_modifiers import PythonModifierEvaluator
from .variable_flow import VariableFlowEvaluator

# Registry of evaluators for different rule types.
_EVALUATORS: Dict[str, Any] = {
    "attribute_contract": AttributeContractEvaluator(),
    "api_signature": ApiSignatureEvaluator(),
    "enum_type": EnumTypeEvaluator(),
    "import_policy": ImportPolicyEvaluator(),
    "member_absence": MemberAbsenceEvaluator(),
    "method_set": MethodSetEvaluator(),
    "nominal_type_relationship": NominalTypeRelationshipEvaluator(),
    "python_modifier": PythonModifierEvaluator(),
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
