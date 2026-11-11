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


def _unverified_reasons(details: Dict[str, Any]) -> list[str]:
    """What a passing runtime result left unchecked, as stable reason codes."""
    coverage = details.get("coverage") or {}
    checks = (
        ("unexercised_lines", coverage.get("unexercised_lines")),
        ("unchecked_stages", details.get("unchecked_stages")),
        ("reference_calls_not_made", details.get("absences")),
        ("calls_not_observable", details.get("unobserved_calls")),
        (
            "case_raised",
            any(
                isinstance(case, dict) and case.get("raised")
                for case in details.get("cases") or []
            ),
        ),
    )
    return [reason for reason, present in checks if present]


def _has_caveat(details: Dict[str, Any]) -> bool:
    """Whether a passing runtime result left something unchecked."""
    return bool(details.get("summary")) and bool(_unverified_reasons(details))


def build_rule_result(
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
        # A runtime pass holds for what ran; say so when something did not.
        message = f"OK: {details['summary']}" if _has_caveat(details) else "OK"
        reasons = _unverified_reasons(details)
        if reasons:
            details = {**details, "unverified": reasons}
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


MAX_REPORTED = 25
"""How many violations (and other listed findings) a result keeps in full."""


def finish_violations(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    details: Dict[str, Any],
    violations: list[str],
    passed: str,
) -> RuleResult:
    """FAILED with the first ``violations`` reported, or OK summarised as ``passed``."""
    if violations:
        details["violations"] = violations[:MAX_REPORTED]
        details["violation_count"] = len(violations)
        details["reason"] = "violation"
        more = f" (+{len(violations) - 1} more)" if len(violations) > 1 else ""
        details["summary"] = violations[0] + more
        return build_rule_result(rule, source, target, match, "FAILED", details, ())
    details["reason"] = "no_violations"
    details["summary"] = passed
    return build_rule_result(rule, source, target, match, "OK", details, ())


__all__ = [
    "MAX_REPORTED",
    "finish_violations",
    "render_message",
    "build_rule_result",
]
