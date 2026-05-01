from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from pythonarchtesting.entities import Entity


def canonicalize_payload(value: Any) -> Any:
    """Canonicalize a payload value for consistent hashing."""
    if isinstance(value, dict):
        return {k: canonicalize_payload(value[k]) for k in sorted(value.keys())}
    if isinstance(value, (list, tuple)):
        items = [canonicalize_payload(item) for item in value]

        def _canonical_json(v: Any) -> str:
            return json.dumps(
                v, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            )

        return sorted(items, key=_canonical_json)

    def _safe_json_value(raw: Any) -> Any:
        try:
            json.dumps(raw)
            return raw
        except TypeError:
            return repr(raw)

    return _safe_json_value(value)


def evidence_id(type_: str, payload: Dict[str, Any]) -> str:
    """Generate evidence ID from type and payload."""

    def _canonical_json(value: Any) -> str:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )

    canonical = _canonical_json(
        {"type": type_, "payload": canonicalize_payload(payload)}
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def with_rule_id_suffix(rule_id: str, suffix: str = "") -> str:
    """Append a deterministic declaration suffix to a rule ID when needed."""
    if not suffix:
        return rule_id
    return f"{rule_id}{suffix}"


def build_invalid_param_sentinel_rule(
    source_entity: Entity,
    *,
    decorator_name: str,
    rule_id_prefix: str,
    param: str,
    value: Any = None,
    valid: list[str] | None = None,
    reason: str | None = None,
    rule_id_suffix: str = "",
) -> Any:
    """Build a sentinel Rule that surfaces a dropped rule at evaluation time.

    Without this sentinel, an invalid-param diagnostic would emit only
    compiler evidence, leaving the dropped rule invisible in
    ``status_counts``. The sentinel is dispatched to
    :class:`CompilerInvalidParamEvaluator`, which always returns FAILED.

    Parameters
    ----------
    decorator_name:
        Public marker name (e.g. ``"required_factory"``,
        ``"require_method_set"``). Stamped into ``params["decorator"]``
        and used in ``rule.name`` and the message template.
    rule_id_prefix:
        Stable prefix for the sentinel's ``rule_id``, e.g.
        ``"API005/require_method_set/invalid_declaration"``. The ``param``
        name is appended; ``rule_id_suffix`` is appended after that.
    """
    from pythonarchtesting.core.models import Rule, RuleSelector

    selector = RuleSelector(
        source_entity_id=source_entity.canonical_id,
        explicit_target=None,
    )
    params: Dict[str, Any] = {
        "decorator": decorator_name,
        "param": param,
        "value": value,
        "valid": list(valid) if valid is not None else [],
        "compiler_reason": reason,
        "fail_on_unmatched": True,
    }
    if valid:
        fix_hint = f"Use one of: {', '.join(sorted(valid))}"
    elif reason:
        fix_hint = reason
    else:
        fix_hint = "Provide a valid value for the parameter."
    return Rule(
        rule_id=with_rule_id_suffix(
            f"{rule_id_prefix}/{param}",
            rule_id_suffix,
        ),
        rule_type="compiler_invalid_param",
        name=decorator_name,
        severity="error",
        scope=source_entity.kind,
        evidence_type="static",
        selector=selector,
        params=params,
        message_template=(
            f"{decorator_name} parameter {{details.param}} is invalid; "
            "the rule was dropped at compile time."
        ),
        fix_hints=(fix_hint,),
        enabled=True,
    )


__all__ = [
    "build_invalid_param_sentinel_rule",
    "canonicalize_payload",
    "evidence_id",
    "with_rule_id_suffix",
]
