"""
Compatibility re-export for unified rule data models.

``pythonarchtesting.core.models`` is the canonical implementation. This module exists so the
``pythonarchtesting.rules.*`` package can keep stable imports while sharing the exact same
class objects (important for type checks, equality, and backward compatibility).
"""

from __future__ import annotations

from pythonarchtesting.core.models import (  # noqa: F401
    ArchRule,
    EvalContext,
    Evidence,
    EvidenceSource,
    EvidenceType,
    Rule,
    RuleEvaluator,
    RuleResult,
    RuleSelector,
    RuleStatus,
    Scope,
    Severity,
)

__all__ = [
    "Severity",
    "Scope",
    "EvidenceType",
    "EvidenceSource",
    "RuleStatus",
    "RuleSelector",
    "Rule",
    "Evidence",
    "RuleResult",
    "EvalContext",
    "ArchRule",
    "RuleEvaluator",
]
