from __future__ import annotations

from typing import Any, Dict, Literal, Tuple


def create_arch_rule(
    rule_id: str,
    kind: str,
    params: Dict[str, Any],
    message_template: str,
    fix_hints: Tuple[str, ...],
    evidence_types: Tuple[str, ...],
    severity: Literal["info", "warning", "error"] = "error",
    min_runtime_mode: str = "static-only",
) -> Any:
    """
    Create an architecture rule with the given parameters.

    Args:
        rule_id: Unique rule identifier
        kind: Rule kind/type
        params: Rule parameters
        message_template: Template for error messages
        fix_hints: Hints for fixing violations
        evidence_types: Types of evidence this rule processes
        severity: Rule severity level
        min_runtime_mode: Minimum runtime mode required for evaluation

    Returns:
        ArchRule instance
    """
    from pythonarchtesting.core.models import ArchRule

    return ArchRule(
        rule_id=rule_id,
        kind=kind,
        scope=None,
        severity=severity,
        source_entity_id="",
        params=params,
        message_template=message_template,
        fix_hints=fix_hints,
        evidence_type="static",
        evidence_types=evidence_types,
        min_runtime_mode=min_runtime_mode,
        enabled=True,
    )


__all__ = ["create_arch_rule"]
