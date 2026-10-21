from __future__ import annotations

from typing import Any, Dict

from .api_signature import ApiSignatureEvaluator
from .attribute_contract import AttributeContractEvaluator
from .compiler_invalid_param import CompilerInvalidParamEvaluator
from .enum_type import EnumTypeEvaluator
from .import_policy import ImportPolicyEvaluator
from .member_absence import MemberAbsenceEvaluator
from .member_set import MemberSetEvaluator
from .method_set import MethodSetEvaluator
from .nominal_type_relationship import NominalTypeRelationshipEvaluator
from .protocol_conformance import ProtocolConformanceEvaluator
from .python_modifiers import PythonModifierEvaluator
from .runtime_flow import RuntimeFlowEvaluator
from .runtime_imports import RuntimeImportsEvaluator
from .runtime_structure import (
    RuntimeCallsEvaluator,
    RuntimeClassKindEvaluator,
    RuntimeInstancesEvaluator,
    RuntimeMembersEvaluator,
    RuntimePatternEvaluator,
    RuntimeProtocolEvaluator,
    RuntimeReferenceCallsEvaluator,
    RuntimeWritesEvaluator,
)
from .variable_flow import VariableFlowEvaluator

# Registry of evaluators for different rule types.
_EVALUATORS: Dict[str, Any] = {
    "attribute_contract": AttributeContractEvaluator(),
    "api_signature": ApiSignatureEvaluator(),
    "compiler_invalid_param": CompilerInvalidParamEvaluator(),
    "enum_type": EnumTypeEvaluator(),
    "import_policy": ImportPolicyEvaluator(),
    "member_absence": MemberAbsenceEvaluator(),
    "member_set": MemberSetEvaluator(),
    "method_set": MethodSetEvaluator(),
    "nominal_type_relationship": NominalTypeRelationshipEvaluator(),
    "python_modifier": PythonModifierEvaluator(),
    "protocol_conformance": ProtocolConformanceEvaluator(),
    "runtime_calls": RuntimeCallsEvaluator(),
    "runtime_writes": RuntimeWritesEvaluator(),
    "runtime_instances": RuntimeInstancesEvaluator(),
    "runtime_members": RuntimeMembersEvaluator(),
    "runtime_class_kind": RuntimeClassKindEvaluator(),
    "runtime_protocol": RuntimeProtocolEvaluator(),
    "runtime_pattern": RuntimePatternEvaluator(),
    "runtime_reference_calls": RuntimeReferenceCallsEvaluator(),
    "runtime_flow": RuntimeFlowEvaluator(),
    "runtime_imports": RuntimeImportsEvaluator(),
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
