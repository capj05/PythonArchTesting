"""
Core declaration helpers for the rules module.

These helpers produce passive marker objects for use in annotation metadata.
"""

from __future__ import annotations

from typing import Any

from pythonarchtesting.rules.declaration.utils import RuleMarker, RuleSeverity


def _clean_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None}


def _resolve_severity(value: str) -> RuleSeverity:
    return {
        "error": RuleSeverity.ERROR,
        "warning": RuleSeverity.WARNING,
        "info": RuleSeverity.INFO,
    }.get(str(value).lower(), RuleSeverity.ERROR)


def _make_rule_marker(
    kind: str,
    params: dict[str, Any],
    *,
    message: str | None = None,
    severity: RuleSeverity = RuleSeverity.ERROR,
) -> RuleMarker:
    """Build a reusable declaration marker from normalized inputs."""
    return RuleMarker(
        kind=kind,
        params=dict(params),
        message=message,
        severity=severity,
    )


def required_entity_signature(
    *,
    mode: str = "compatible",
    allow_extra_params: bool = True,
    allow_param_rename: bool = False,
    return_annotation: str = "warning",
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture required signature intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "mode": mode,
            "allow_extra_params": allow_extra_params,
            "allow_param_rename": allow_param_rename,
            "return_annotation": return_annotation,
            "severity": severity,
        }
    )
    marker = _make_rule_marker(
        "required_entity_signature",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )
    return marker


def required_method(
    *,
    signature_mode: str = "compatible",
    enforce_method_kind: bool = True,
    allow_missing: bool = False,
    declared_only: bool = False,
    name_match: str = "exact",
    aliases: list[str] | None = None,
    pattern: str | None = None,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture required method intent for the rule engine.

    ``signature_mode`` accepts ``"compatible"``, ``"exact"``, and ``"any"``.
    ``"any"`` keeps the method existence check but ignores parameter shape.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "signature_mode": signature_mode,
            "enforce_method_kind": enforce_method_kind,
            "allow_missing": allow_missing,
            "declared_only": declared_only,
            "name_match": name_match,
            "aliases": list(aliases) if aliases is not None else None,
            "pattern": pattern,
            "severity": severity,
        }
    )
    marker = _make_rule_marker(
        "required_method",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )
    return marker


def required_constructor(
    *,
    signature_mode: str = "compatible",
    constructor_kind: str = "auto",
    allow_inherited: bool = True,
    allow_missing: bool = False,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture required constructor intent for the rule engine.

    Place on a class-level ``__archtest__`` annotation. The evaluator resolves
    the source class constructor (``__init__`` or ``__new__`` depending on
    ``constructor_kind``) and checks that the matched target class exposes a
    compatible constructor. Statically recognizable dataclass-generated
    ``__init__`` methods participate as constructor contracts and target
    candidates.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "signature_mode": signature_mode,
            "constructor_kind": constructor_kind,
            "allow_inherited": allow_inherited,
            "allow_missing": allow_missing,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "required_constructor",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def required_factory(
    *,
    signature_mode: str = "compatible",
    satisfy_with: tuple[str, ...] = ("constructor", "classmethod", "staticmethod"),
    allow_inherited: bool = True,
    name_match: str = "any",
    aliases: list[str] | None = None,
    pattern: str | None = None,
    allow_missing: bool = False,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture required factory intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "signature_mode": signature_mode,
            "satisfy_with": list(satisfy_with),
            "allow_inherited": allow_inherited,
            "name_match": name_match,
            "aliases": list(aliases) if aliases is not None else None,
            "pattern": pattern,
            "allow_missing": allow_missing,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "required_factory",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def required_attribute(
    name: str,
    *,
    annotation: str | None = None,
    storage: str = "any",
    allow_property: bool = False,
    require_writable: bool = False,
    declared_only: bool = False,
    allow_missing: bool = False,
    descriptor_kinds: tuple[str, ...] | None = None,
    include_dynamic_attributes: bool = False,
    interpret_dataclass_fields: bool = False,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture required attribute intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "name": name,
            "annotation": annotation,
            "storage": storage,
            "allow_property": allow_property,
            "require_writable": require_writable,
            "declared_only": declared_only,
            "allow_missing": allow_missing,
            "severity": severity,
        }
    )
    if descriptor_kinds is not None:
        cleaned["descriptor_kinds"] = tuple(descriptor_kinds)
    if include_dynamic_attributes:
        cleaned["include_dynamic_attributes"] = True
    if interpret_dataclass_fields:
        cleaned["interpret_dataclass_fields"] = True
    return _make_rule_marker(
        "required_attribute",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def does_not_have(
    name: str | None = None,
    *,
    member_kind: str = "any",
    storage: str = "any",
    declared_only: bool = False,
    name_match: str = "exact",
    aliases: list[str] | None = None,
    pattern: str | None = None,
    signature_mode: str = "any",
    include_descriptors: bool = False,
    include_dynamic_attributes: bool = False,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture forbidden class-member intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "name": name,
            "member_kind": member_kind,
            "storage": storage,
            "declared_only": declared_only,
            "severity": severity,
        }
    )
    if name_match != "exact":
        cleaned["name_match"] = name_match
    if aliases is not None:
        cleaned["aliases"] = list(aliases)
    if pattern is not None:
        cleaned["pattern"] = pattern
    if signature_mode != "any":
        cleaned["signature_mode"] = signature_mode
    if include_descriptors:
        cleaned["include_descriptors"] = True
    if include_dynamic_attributes:
        cleaned["include_dynamic_attributes"] = True
    return _make_rule_marker(
        "does_not_have",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def forbid_imports(
    *forbidden: str,
    scope: str = "package",
    package: str | None = None,
    mode: str = "reachable",
    ignore_type_checking: bool = True,
    allow: list[str] | None = None,
    ignore_globs: list[str] | None = None,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture forbidden import policy for the rule engine.

    Canonical scope values are ``"module"`` and ``"package"``. The legacy
    ``"entity"`` input is still accepted for backward compatibility and is
    normalized during rule compilation.

    Defaults to ``mode="reachable"`` for graph-based reachable-import
    analysis. Use ``mode="direct"`` to opt into the direct AST import check.
    This helper is declaration-only and returns passive annotation metadata.
    """
    if mode not in {"reachable", "direct"}:
        raise ValueError("forbid_imports() mode must be 'reachable' or 'direct'.")
    cleaned = _clean_kwargs(
        {
            "forbidden": list(forbidden),
            "scope": scope,
            "package": package,
            "mode": mode,
            "ignore_type_checking": ignore_type_checking,
            "allow": list(allow or []),
            "ignore_globs": list(ignore_globs or []),
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "forbid_imports",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def implements_protocol(
    protocol: Any,
    *,
    signature_mode: str = "compatible",
    enforce_method_kind: bool = True,
    return_annotation: str = "warning",
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture protocol-conformance intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "protocol": protocol,
            "signature_mode": signature_mode,
            "enforce_method_kind": enforce_method_kind,
            "return_annotation": return_annotation,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "implements_protocol",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def subclass_of(
    base: str,
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture nominal inheritance intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "base": base,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "subclass_of",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def exact_type(
    base: str,
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture exact nominal type identity intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "base": base,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "exact_type",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def not_subclass_of(
    base: str,
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture forbidden nominal inheritance intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "base": base,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "not_subclass_of",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def inherits_directly_from(
    base: str,
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture direct nominal inheritance intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "base": base,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "inherits_directly_from",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def flow(
    stage: str,
    *,
    variable: str | None = None,
    message: str | None = None,
) -> RuleMarker:
    """
    Capture statement-level flow-stage intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "stage": stage,
            "variable": variable,
        }
    )
    return _make_rule_marker(
        "flow",
        cleaned,
        message=message,
        severity=RuleSeverity.INFO,
    )


def enforce_flow(
    stages: list[str] | tuple[str, ...],
    *,
    variable: str | None = None,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture variable-flow validation intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "stages": list(stages),
            "variable": variable,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "enforce_flow",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )
