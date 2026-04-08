from __future__ import annotations

from string import Formatter
from types import SimpleNamespace
from typing import Any, Dict, Tuple

from pythonarchtesting.core.models import Evidence, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult


def _entity_mapping(entity: Entity | None) -> Dict[str, Any]:
    """Convert entity to dictionary for message formatting."""
    if entity is None:
        return {}
    return {
        "entity_id": entity.canonical_id,
        "module_path": entity.module_path,
        "qualname": entity.qualname,
        "name": entity.name,
        "kind": entity.kind,
        "signature_key": entity.signature_key,
        "filepath": entity.filepath_rel,
        "lineno": entity.lineno,
    }


def _to_namespace(value: Any) -> Any:
    """Convert dictionaries to SimpleNamespace for template formatting."""
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_to_namespace(item) for item in value]
    return value


def _message_mapping(
    rule: Rule,
    source: Entity,
    target: Entity | None,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    """Create mapping for message template formatting."""
    return {
        "source": _to_namespace(_entity_mapping(source)),
        "target": _to_namespace(_entity_mapping(target)),
        "rule": _to_namespace(
            {
                "id": rule.rule_id,
                "type": rule.rule_type,
                "name": rule.name,
                "severity": rule.severity,
            }
        ),
        "details": _to_namespace(details),
    }


def render_message(template: str, mapping: Dict[str, Any]) -> Tuple[str, str | None]:
    """
    Render a message template with the given mapping.

    Args:
        template: Message template string
        mapping: Values for template placeholders

    Returns:
        Tuple of (rendered_message, error_message)
    """
    formatter = Formatter()
    for _, field_name, _, _ in formatter.parse(template):
        if not field_name:
            continue
        root = field_name.split(".")[0]
        if root not in {"source", "target", "rule", "details"}:
            return "", f"Unsupported placeholder: {field_name}"
    try:
        return template.format_map(mapping), None
    except Exception as exc:
        return "", str(exc)


def _build_rule_result(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    status: RuleStatus,
    details: Dict[str, Any],
    evidence: Tuple[Evidence, ...],
) -> RuleResult:
    """Build a RuleResult from evaluation data."""
    if status == "OK":
        message = "OK"
    else:
        mapping = _message_mapping(rule, source, target, details)
        rendered, error = render_message(rule.message_template, mapping)
        if error is not None:
            return RuleResult(
                rule_id=rule.rule_id,
                status="ERROR",
                source_entity_id=source.canonical_id,
                target_entity_id=target.canonical_id,
                match_status=match.status.value,
                confidence=match.confidence,
                message=f"Message render failed: {error}",
                evidence=evidence,
                details={
                    **details,
                    "template_error": error,
                },
            )
        message = rendered

    return RuleResult(
        rule_id=rule.rule_id,
        status=status,
        source_entity_id=source.canonical_id,
        target_entity_id=target.canonical_id,
        match_status=match.status.value,
        confidence=match.confidence,
        message=message,
        evidence=evidence,
        details=details,
    )


__all__ = ["render_message"]
