from __future__ import annotations

from typing import Any, Dict, Literal, cast

# The payload hashing is the one evidence collection uses: a compiler's
# evidence and a collector's of the same payload get the same id.
from pythonarchtesting.core.evidence import canonicalize_payload, evidence_id
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity


def declaration_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    evidence_type: str,
    payload: Dict[str, Any],
) -> Evidence:
    """The compiler's evidence of type ``evidence_type`` about ``declaration``
    on ``source_entity``, located at the declaration (at the entity when the
    declaration has no line); every marker compiler reports the problems of a
    declaration it drops this way."""
    location = {
        "filepath": source_entity.filepath_rel,
        "lineno": declaration.lineno or source_entity.lineno,
        "col": declaration.col,
    }
    return Evidence(
        evidence_id=evidence_id(evidence_type, payload),
        type=evidence_type,
        source="compiler",
        role="source",
        entity_id=source_entity.canonical_id,
        payload=canonicalize_payload(payload),
        location=location,
    )


def invalid_declaration_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    decorator: str,
    reason: str,
    params: Dict[str, Any],
) -> Evidence:
    """The evidence that the ``decorator`` marker's ``declaration`` was
    dropped: ``reason`` says which parameter is invalid, ``params`` are the
    parameters as declared."""
    payload = {
        "decorator": decorator,
        "issue": "compiler_invalid_declaration",
        "reason": reason,
        "params": params,
    }
    return declaration_evidence(
        source_entity,
        declaration,
        evidence_type="compiler_invalid_declaration",
        payload=payload,
    )


def invalid_target_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    decorator: str,
    expected_kind: str = "class",
    key: str = "decorator",
) -> Evidence:
    """The evidence that the ``decorator`` marker, which checks entities of
    ``expected_kind``, was declared on ``source_entity``, which is of
    another kind. ``key`` is the payload key that names the marker: some
    compilers name it ``declaration``, and the payload is kept as it was."""
    payload = {
        key: decorator,
        "issue": "compiler_invalid_target",
        "expected_kind": expected_kind,
        "found_kind": source_entity.kind,
    }
    return declaration_evidence(
        source_entity,
        declaration,
        evidence_type="compiler_invalid_target",
        payload=payload,
    )


def bool_param(
    params: Dict[str, Any], name: str, *, default: bool
) -> tuple[bool, bool]:
    """The boolean parameter ``name`` (``default`` when absent) and whether it
    is valid; a value that is no ``bool`` is invalid and gives ``default``."""
    value = params.get(name, default)
    if isinstance(value, bool):
        return value, True
    return default, False


def marker_severity(params: Dict[str, Any]) -> Literal["error", "warning", "info"]:
    """The severity a marker declares (``severity=``, any case); ``"error"``
    when it declares none or one that is no severity."""
    raw = str(params.get("severity", "error")).lower()
    if raw in {"error", "warning", "info"}:
        return cast(Literal["error", "warning", "info"], raw)
    return "error"


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
    "bool_param",
    "build_invalid_param_sentinel_rule",
    "canonicalize_payload",
    "declaration_evidence",
    "evidence_id",
    "invalid_declaration_evidence",
    "invalid_target_evidence",
    "marker_severity",
    "with_rule_id_suffix",
]
