"""
Core declaration helpers for the rules module.

These helpers produce passive marker objects for use in annotation metadata.
"""

from __future__ import annotations

from typing import Any

from pythonarchtesting.rules.declaration.utils import RuleMarker, RuleSeverity


class _HelperDefaultStr(str):
    """Sentinel string that preserves readable signatures for omitted args."""


_REQUIRED_FACTORY_RETURN_DEFAULT = _HelperDefaultStr("ignore")
_REQUIRED_FACTORY_DETECTION_DEFAULT = _HelperDefaultStr("strict")


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


def require_method_set(
    *,
    name_match: str = "any",
    names: list[str] | None = None,
    pattern: str | None = None,
    declared_only: bool = False,
    method_kind: str = "any",
    min_count: int = 1,
    max_count: int | None = None,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture bulk method-selection intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "name_match": name_match,
            "names": list(names) if names is not None else None,
            "pattern": pattern,
            "declared_only": declared_only,
            "method_kind": method_kind,
            "min_count": min_count,
            "max_count": max_count,
            "severity": severity,
        }
    )
    marker = _make_rule_marker(
        "require_method_set",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )
    return marker


def require_member_set(
    *,
    member_kinds: tuple[str, ...] = ("any",),
    name_match: str = "any",
    names: list[str] | None = None,
    pattern: str | None = None,
    declared_only: bool = False,
    method_kind: str = "any",
    storage: str = "any",
    allow_property: bool = True,
    descriptor_kinds: tuple[str, ...] | None = None,
    include_dynamic_attributes: bool = False,
    interpret_dataclass_fields: bool = False,
    constructor_kind: str = "auto",
    include_dataclass_constructor: bool = True,
    min_count: int = 1,
    max_count: int | None = None,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture bulk member-selection intent for the rule engine.

    Generalises ``require_method_set`` to additionally select attributes,
    properties, descriptors, and constructors. v1 is cardinality-only — no
    nested per-member rules. Class-level only.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "member_kinds": list(member_kinds),
            "name_match": name_match,
            "names": list(names) if names is not None else None,
            "pattern": pattern,
            "declared_only": declared_only,
            "method_kind": method_kind,
            "storage": storage,
            "allow_property": allow_property,
            "descriptor_kinds": (
                list(descriptor_kinds) if descriptor_kinds is not None else None
            ),
            "include_dynamic_attributes": include_dynamic_attributes,
            "interpret_dataclass_fields": interpret_dataclass_fields,
            "constructor_kind": constructor_kind,
            "include_dataclass_constructor": include_dataclass_constructor,
            "min_count": min_count,
            "max_count": max_count,
            "severity": severity,
        }
    )
    marker = _make_rule_marker(
        "require_member_set",
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
    return_annotation_mode: str = _REQUIRED_FACTORY_RETURN_DEFAULT,
    detection_mode: str = _REQUIRED_FACTORY_DETECTION_DEFAULT,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture required factory intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned_payload = {
        "signature_mode": signature_mode,
        "satisfy_with": list(satisfy_with),
        "allow_inherited": allow_inherited,
        "name_match": name_match,
        "aliases": list(aliases) if aliases is not None else None,
        "pattern": pattern,
        "allow_missing": allow_missing,
        "severity": severity,
    }
    if type(return_annotation_mode) is not _HelperDefaultStr:
        cleaned_payload["return_annotation_mode"] = return_annotation_mode
    if type(detection_mode) is not _HelperDefaultStr:
        cleaned_payload["detection_mode"] = detection_mode
    cleaned = _clean_kwargs(cleaned_payload)
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


def is_enum(
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture enum-classification intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "is_enum",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def _runtime_calls_marker(
    name: str,
    modules: tuple[str, ...],
    *,
    cases: list[dict[str, Any]],
    allow: list[str] | None,
    init: dict[str, Any] | None,
    timeout_s: float,
    severity: str,
    message: str | None,
    transitive: bool = False,
    through: list[str] | None = None,
) -> RuleMarker:
    cleaned = _clean_kwargs(
        {
            "modules": list(modules),
            "allow": list(allow or []),
            "transitive": transitive or None,
            "through": list(through) if through is not None else None,
            "cases": list(cases),
            "init": dict(init) if init is not None else None,
            "timeout_s": timeout_s,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        name,
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def forbid_runtime_calls(
    *modules: str,
    cases: list[dict[str, Any]],
    allow: list[str] | None = None,
    transitive: bool = False,
    through: list[str] | None = None,
    init: dict[str, Any] | None = None,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture a runtime layering policy for the rule engine.

    The matched target function or method is called once per case, and every
    call that code of its module makes into another module is recorded. Calls
    into the listed modules are violations, including calls that static
    analysis cannot attribute (duck typing, injected objects, ``getattr``).
    Cases only give call arguments; what the call computes is not checked. The
    check only runs when the CLI is started with ``--dynamic``.

    With ``transitive=True`` a call into the listed modules made by any
    project code while the target runs counts too (a detour through a helper
    module), unless that code was reached through a module in ``through`` —
    the layer whose job it is to make the call.

    This helper is declaration-only and returns passive annotation metadata.
    """
    return _runtime_calls_marker(
        "forbid_runtime_calls",
        modules,
        cases=cases,
        allow=allow,
        transitive=transitive,
        through=through,
        init=init,
        timeout_s=timeout_s,
        severity=severity,
        message=message,
    )


def require_runtime_calls(
    *modules: str,
    cases: list[dict[str, Any]],
    init: dict[str, Any] | None = None,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture a runtime delegation policy for the rule engine.

    Like ``forbid_runtime_calls``, but code of the target's module must call
    into each listed module directly in every case, so the work is delegated
    to that layer rather than done in place. The check only runs when the CLI
    is started with ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    return _runtime_calls_marker(
        "require_runtime_calls",
        modules,
        cases=cases,
        allow=None,
        init=init,
        timeout_s=timeout_s,
        severity=severity,
        message=message,
    )


def forbid_runtime_instantiation(
    *modules: str,
    cases: list[dict[str, Any]],
    allow: list[str] | None = None,
    transitive: bool = False,
    through: list[str] | None = None,
    init: dict[str, Any] | None = None,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture a dependency-injection policy for the rule engine.

    The matched target function or method is called once per case (a method's
    instance is built first, and that counts too). Code of its module must not
    create instances of classes defined in the listed modules: it has to
    receive such objects from its caller. Calling their methods stays allowed.
    The check only runs when the CLI is started with ``--dynamic``.

    With ``transitive=True`` an instance any project code builds while the
    target runs counts too (a factory module of its own), unless it was built
    by code of a module in ``through``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    return _runtime_calls_marker(
        "forbid_runtime_instantiation",
        modules,
        cases=cases,
        allow=allow,
        transitive=transitive,
        through=through,
        init=init,
        timeout_s=timeout_s,
        severity=severity,
        message=message,
    )


def enforce_reference_calls(
    *,
    cases: list[dict[str, Any]],
    require_all: bool = False,
    allow_new_modules: bool = False,
    init: dict[str, Any] | None = None,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture a reference-derived layering policy for the rule engine.

    The reference entity and the matched target are called with the same
    cases, and every call between two different modules of the project is
    recorded. The target must not make a module-to-module call the reference
    does not make; with ``require_all`` it must also make every one the
    reference makes. With ``allow_new_modules`` a module the reference does
    not have counts as part of the modules that call it. The check only runs
    when the CLI is started with ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "cases": list(cases),
            "require_all": require_all,
            "allow_new_modules": allow_new_modules or None,
            "init": dict(init) if init is not None else None,
            "timeout_s": timeout_s,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "enforce_reference_calls",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def _runtime_class_marker(
    name: str,
    kwargs: dict[str, Any],
    *,
    severity: str,
    message: str | None,
) -> RuleMarker:
    cleaned = _clean_kwargs({**kwargs, "severity": severity})
    return _make_rule_marker(
        name,
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def require_runtime_members(
    *names: str,
    cases: list[dict[str, Any]],
    types: dict[str, str] | None = None,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture a runtime member requirement for the rule engine.

    An instance of the matched target class is built from each case's
    constructor arguments and must have every listed member, however it got
    there: assigned in ``__init__``, through ``setattr`` in a loop,
    ``__dict__.update``, a mixin, a decorator, or a base class from a library.
    ``types`` maps a listed name to a class (``"repository.OrderRepository"``)
    whose instance, or a subclass's, the member must hold. The check only runs
    when the CLI is started with ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    return _runtime_class_marker(
        "require_runtime_members",
        {
            "names": list(names),
            "types": dict(types) if types is not None else None,
            "cases": list(cases),
            "timeout_s": timeout_s,
        },
        severity=severity,
        message=message,
    )


def forbid_runtime_members(
    *names: str,
    cases: list[dict[str, Any]],
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture a runtime member prohibition for the rule engine.

    Like ``require_runtime_members``, but an instance built from any case must
    not have any of the listed members. The check only runs when the CLI is
    started with ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    return _runtime_class_marker(
        "forbid_runtime_members",
        {"names": list(names), "cases": list(cases), "timeout_s": timeout_s},
        severity=severity,
        message=message,
    )


def is_runtime_concrete_class(
    *,
    cases: list[dict[str, Any]],
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture a runtime instantiability requirement for the rule engine.

    The matched target class must be instantiable from each case's constructor
    arguments. Python decides abstractness, so abstract methods inherited from
    bases outside the project (``collections.abc``, a framework) count. The
    check only runs when the CLI is started with ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    return _runtime_class_marker(
        "is_runtime_concrete_class",
        {"cases": list(cases), "timeout_s": timeout_s},
        severity=severity,
        message=message,
    )


def is_runtime_abstract_class(
    *,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture a runtime abstractness requirement for the rule engine.

    The matched target class is imported and must be abstract as Python sees
    it (``inspect.isabstract``), bases outside the project included. Nothing
    is instantiated. The check only runs when the CLI is started with
    ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    return _runtime_class_marker(
        "is_runtime_abstract_class",
        {"timeout_s": timeout_s},
        severity=severity,
        message=message,
    )


def implements_runtime_protocol(
    protocol: Any,
    *,
    cases: list[dict[str, Any]],
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture a runtime protocol conformance requirement for the rule engine.

    An instance of the matched target class is built from each case and must
    have every member of the protocol, with methods callable with the
    protocol's positional arguments — wherever they come from at run time.
    The check only runs when the CLI is started with ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    return _runtime_class_marker(
        "implements_runtime_protocol",
        {
            "protocol": protocol,
            "cases": list(cases),
            "timeout_s": timeout_s,
        },
        severity=severity,
        message=message,
    )


def is_runtime_singleton(
    *,
    cases: list[dict[str, Any]],
    access: str | None = None,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture a Singleton requirement for the rule engine.

    The instance of the matched target class is obtained twice per case —
    through the class method named by ``access`` (``Config.instance()``), a
    function of the class's module of that name (``get_config()``), or by
    calling the class itself — and both must be the same object. The check
    only runs when the CLI is started with ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    return _runtime_class_marker(
        "is_runtime_singleton",
        {"cases": list(cases), "access": access, "timeout_s": timeout_s},
        severity=severity,
        message=message,
    )


def enforce_runtime_observer(
    *,
    subscribe: str,
    notify: str,
    cases: list[dict[str, Any]],
    notify_args: list[Any] | None = None,
    unsubscribe: str | None = None,
    subscribe_args: list[Any] | None = None,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture an Observer requirement for the rule engine.

    An instance of the matched target class is built per case, a recording
    listener is registered through ``subscribe``, and ``notify`` is called
    with ``notify_args``: the listener must be called. With ``unsubscribe``
    the listener is removed and a second notification must not reach it.
    ``subscribe_args`` go before the listener in ``subscribe`` and
    ``unsubscribe``, for a subject keyed by event (``subscribe("created",
    fn)``). The check only runs when the CLI is started with ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    return _runtime_class_marker(
        "enforce_runtime_observer",
        {
            "subscribe": subscribe,
            "notify": notify,
            "unsubscribe": unsubscribe,
            "notify_args": list(notify_args or []),
            "subscribe_args": list(subscribe_args or []),
            "cases": list(cases),
            "timeout_s": timeout_s,
        },
        severity=severity,
        message=message,
    )


def require_runtime_delegation(
    spy: str,
    *,
    cases: list[dict[str, Any]],
    member: str | None = None,
    init: dict[str, Any] | None = None,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture a delegation requirement (Strategy, Decorator, Proxy) for the rule engine.

    The cases inject a recording stand-in with ``{"$spy": spy}`` in the call
    or constructor arguments. While the matched target function or method
    runs, it must call that collaborator — ``member`` on it, if given. The
    check only runs when the CLI is started with ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    return _runtime_class_marker(
        "require_runtime_delegation",
        {
            "spy": spy,
            "member": member,
            "cases": list(cases),
            "init": dict(init) if init is not None else None,
            "timeout_s": timeout_s,
        },
        severity=severity,
        message=message,
    )


def forbid_foreign_writes(
    *,
    cases: list[dict[str, Any]],
    init: dict[str, Any] | None = None,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture an encapsulation policy for the rule engine.

    The matched target function or method is called once per case. While it
    runs, an attribute of an object whose class is defined in the target may
    only be assigned by that class's own methods; ``order.total = ...`` from
    outside ``Order`` is a violation. Cases only give call arguments. The
    check only runs when the CLI is started with ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "cases": list(cases),
            "init": dict(init) if init is not None else None,
            "timeout_s": timeout_s,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "forbid_foreign_writes",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def forbid_runtime_imports(
    *forbidden: str,
    allow: list[str] | None = None,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture runtime import policy for the rule engine.

    The matched target module is imported in a child interpreter and every
    import its code performs is recorded, including ``importlib.import_module``
    and ``__import__`` calls that static analysis cannot see. The check only
    runs when the CLI is started with ``--dynamic``.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "forbidden": list(forbidden),
            "allow": list(allow or []),
            "timeout_s": timeout_s,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "forbid_runtime_imports",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def is_abstract_class(
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture abstract-class intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "is_abstract_class",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def is_abstract_method(
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture abstract-method intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "is_abstract_method",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def is_concrete_class(
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture concrete-class intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "is_concrete_class",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def is_final_class(
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture final-class intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "is_final_class",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def is_final_method(
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture final-method intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "is_final_method",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def is_non_final_class(
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture non-final-class intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "is_non_final_class",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def is_non_abstract_method(
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture non-abstract-method intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "is_non_abstract_method",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )


def is_non_final_method(
    *,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture non-final-method intent for the rule engine.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "is_non_final_method",
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
    cases: list[dict[str, Any]] | None = None,
    init: dict[str, Any] | None = None,
    timeout_s: float = 5.0,
    severity: str = "error",
    message: str | None = None,
) -> RuleMarker:
    """
    Capture variable-flow validation intent for the rule engine.

    Without ``cases`` the target must carry its own ``flow(...)`` markers, which
    are checked statically. With ``cases`` (call arguments only) the check runs
    with ``--dynamic`` instead: the reference is executed to learn which of
    the project's functions each stage calls, and the target must call them
    in the same stage order. Values are never compared. The target then needs
    no markers.

    This helper is declaration-only and returns passive annotation metadata.
    """
    cleaned = _clean_kwargs(
        {
            "stages": list(stages),
            "variable": variable,
            "cases": list(cases) if cases is not None else None,
            "init": dict(init) if init is not None else None,
            "timeout_s": timeout_s if cases is not None else None,
            "severity": severity,
        }
    )
    return _make_rule_marker(
        "enforce_flow",
        cleaned,
        message=message,
        severity=_resolve_severity(severity),
    )
