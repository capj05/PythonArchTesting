from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence, Rule, RuleSelector
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    build_invalid_param_sentinel_rule,
    canonicalize_payload,
    evidence_id,
    with_rule_id_suffix,
)

_SUPPORTED_KINDS = frozenset({"function", "method"})
_RUNTIME_CASE_KEYS = frozenset({"args", "kwargs", "init", "steps", "stdin"})
_STEP_KEYS = frozenset({"call", "args", "kwargs"})
_SPY_KEYS = frozenset({"$spy", "returns"})
_MAX_TIMEOUT_S = 60.0

# marker name -> (rule id, rule type, whether the listed modules are
# forbidden or required, fix hint)
_MODULE_LIST_MARKERS = {
    "forbid_runtime_calls": (
        "DYN001/forbid_runtime_calls/v1",
        "runtime_calls",
        "forbid",
        "Route the call through the layer the reference uses instead of "
        "calling the forbidden module directly.",
    ),
    "require_runtime_calls": (
        "DYN001/require_runtime_calls/v1",
        "runtime_calls",
        "require",
        "Delegate to the required module the way the reference does instead "
        "of doing its work in place.",
    ),
    "forbid_runtime_instantiation": (
        "DYN004/forbid_runtime_instantiation/v1",
        "runtime_instances",
        "forbid",
        "Receive the object from the caller (constructor or function "
        "argument) instead of creating it here.",
    ),
}


def _evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    evidence_type: str,
    payload: dict[str, Any],
) -> Evidence:
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


def _severity(params: dict[str, Any]) -> Literal["error", "warning", "info"]:
    raw = str(params.get("severity", "error")).lower()
    if raw in {"error", "warning", "info"}:
        return cast(Literal["error", "warning", "info"], raw)
    return "error"


def _transport_problem(value: Any) -> str | None:
    """Reject values that would not survive the JSON trip to the child unchanged."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            problem = _transport_problem(item)
            if problem:
                return problem
        return None
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                return f"dict key {key!r} is not a string"
            problem = _transport_problem(item)
            if problem:
                return problem
        return None
    return f"{type(value).__name__} value {value!r} is not supported"


def _init_problem(init: Any) -> str | None:
    if not isinstance(init, dict):
        return "init must be a dict with optional 'args' and 'kwargs'"
    problem = _transport_problem(init)
    if problem:
        return f"init: {problem}"
    unknown = sorted(set(init) - {"args", "kwargs"})
    if unknown:
        return f"init has unknown keys: {', '.join(unknown)}"
    if not isinstance(init.get("args", []), list):
        return "init['args'] must be a list"
    if not isinstance(init.get("kwargs", {}), dict):
        return "init['kwargs'] must be a dict"
    return None


def _steps_problem(steps: Any) -> str | None:
    """``steps``: methods of the same instance called to prepare its state."""
    if not isinstance(steps, list):
        return "'steps' must be a list of {'call': name, 'args', 'kwargs'}"
    for number, step in enumerate(steps):
        if not isinstance(step, dict) or not str(step.get("call") or "").isidentifier():
            return f"step {number} needs 'call', the name of a method"
        unknown = sorted(set(step) - _STEP_KEYS)
        if unknown:
            return f"step {number} has unknown keys: {', '.join(unknown)}"
        if not isinstance(step.get("args", []), list):
            return f"step {number} 'args' must be a list"
        if not isinstance(step.get("kwargs", {}), dict):
            return f"step {number} 'kwargs' must be a dict"
    return None


def _spy_problem(value: Any) -> str | None:
    """A ``{"$spy": name}`` value, optionally with ``returns`` per member."""
    if isinstance(value, list):
        return next(filter(None, (_spy_problem(item) for item in value)), None)
    if not isinstance(value, dict):
        return None
    if "$spy" in value:
        if not isinstance(value["$spy"], str) or not value["$spy"]:
            return "a spy needs a name: {'$spy': 'name'}"
        unknown = sorted(set(value) - _SPY_KEYS)
        if unknown:
            return f"spy {value['$spy']!r} has unknown keys: {', '.join(unknown)}"
        if not isinstance(value.get("returns", {}), dict):
            return f"spy {value['$spy']!r}: 'returns' must be a dict of member -> value"
    return next(filter(None, (_spy_problem(item) for item in value.values())), None)


def runtime_cases_problem(
    params: dict[str, Any], kind: str, marker: str
) -> tuple[str, str] | None:
    """Validate ``cases`` and ``timeout_s`` of a marker that runs target code.

    Cases only give call arguments (and ``stdin``, the text the target reads
    from the keyboard): they drive execution so the structure can be observed,
    and never state what the call should compute.
    """
    cases = params.get("cases")
    if not isinstance(cases, list) or not cases:
        return "cases", "cases must be a non-empty list of dicts"
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            return "cases", f"case {index} must be a dict"
        unknown = sorted(set(case) - _RUNTIME_CASE_KEYS)
        if unknown:
            return (
                "cases",
                f"case {index} has unknown keys: {', '.join(unknown)}; "
                f"{marker} cases only give call arguments",
            )
        problem = _transport_problem(case) or _spy_problem(case)
        if problem:
            return "cases", f"case {index}: {problem}"
        if "steps" in case:
            if kind not in ("method", "class"):
                return "cases", f"case {index} uses 'steps', which need an instance"
            problem = _steps_problem(case["steps"])
            if problem:
                return "cases", f"case {index}: {problem}"
        if not isinstance(case.get("args", []), list):
            return "cases", f"case {index} 'args' must be a list"
        if not isinstance(case.get("kwargs", {}), dict):
            return "cases", f"case {index} 'kwargs' must be a dict"
        if not isinstance(case.get("stdin", ""), str):
            return "cases", f"case {index}: stdin must be a string"
        if "init" in case:
            if kind != "method":
                return "cases", f"case {index} uses 'init', which only methods support"
            problem = _init_problem(case["init"])
            if problem:
                return "cases", f"case {index}: {problem}"
    init = params.get("init")
    if init is not None:
        if kind != "method":
            return "init", "init only applies to methods"
        problem = _init_problem(init)
        if problem:
            return "init", problem
    timeout_s = params.get("timeout_s", 5.0)
    if (
        isinstance(timeout_s, bool)
        or not isinstance(timeout_s, (int, float))
        or not 0 < timeout_s <= _MAX_TIMEOUT_S
    ):
        return "timeout_s", f"timeout_s must be a number in (0, {_MAX_TIMEOUT_S:g}]"
    return None


def _module_names(value: Any) -> list[str] | None:
    if not isinstance(value, (list, tuple)):
        return None
    if not all(isinstance(name, str) and name for name in value):
        return None
    return [str(name) for name in value]


def _invalid_target(
    source_entity: Entity, declaration: DeclarationEntry, marker: str, expected: Any
) -> Tuple[List[Any], List[Any], List[Any]]:
    payload = {
        "declaration": marker,
        "issue": "compiler_invalid_target",
        "expected_kind": expected,
        "found_kind": source_entity.kind,
    }
    return (
        [],
        [
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_target",
                payload=payload,
            )
        ],
        [],
    )


def _invalid_param(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    marker: str,
    rule_id_prefix: str,
    problem: tuple[str, str],
    rule_id_suffix: str,
) -> Tuple[List[Any], List[Any], List[Any]]:
    param, reason = problem
    payload = {
        "decorator": marker,
        "issue": "compiler_invalid_param",
        "param": param,
        "reason": reason,
    }
    sentinel = build_invalid_param_sentinel_rule(
        source_entity,
        decorator_name=marker,
        rule_id_prefix=rule_id_prefix,
        param=param,
        reason=reason,
        rule_id_suffix=rule_id_suffix,
    )
    return (
        [sentinel],
        [
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_param",
                payload=payload,
            )
        ],
        [],
    )


def _case_params(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "cases": params["cases"],
        "init": params.get("init"),
        "timeout_s": float(params.get("timeout_s", 5.0)),
        "fail_on_unmatched": True,
    }


def _compile_module_list(
    marker: str,
    source_entity: Entity,
    declaration: DeclarationEntry,
    rule_id_suffix: str,
) -> Tuple[List[Any], List[Any], List[Any]]:
    rule_id, rule_type, mode, hint = _MODULE_LIST_MARKERS[marker]
    params_kwargs = dict(declaration.params)
    if source_entity.kind not in _SUPPORTED_KINDS:
        return _invalid_target(
            source_entity, declaration, marker, sorted(_SUPPORTED_KINDS)
        )

    modules = _module_names(params_kwargs.get("modules", []))
    allow = _module_names(params_kwargs.get("allow") or [])
    transitive = params_kwargs.get("transitive", False)
    through = _module_names(params_kwargs.get("through") or [])
    cover_module = params_kwargs.get("cover_module", False)
    problem: tuple[str, str] | None = None
    if not isinstance(cover_module, bool):
        problem = ("cover_module", "cover_module must be True or False")
    elif cover_module and marker != "forbid_runtime_calls":
        problem = ("cover_module", f"cover_module does not apply to {marker}")
    elif not modules:
        problem = ("modules", "give at least one module name")
    elif allow is None:
        problem = ("allow", "allow must be a list of module names")
    elif mode == "require" and allow:
        problem = ("allow", f"allow does not apply to {marker}")
    elif not isinstance(transitive, bool):
        problem = ("transitive", "transitive must be True or False")
    elif transitive and mode != "forbid":
        problem = ("transitive", f"transitive does not apply to {marker}")
    elif through is None:
        problem = ("through", "through must be a list of module names")
    elif through and not transitive:
        problem = ("through", "through applies only with transitive=True")
    else:
        problem = runtime_cases_problem(params_kwargs, source_entity.kind, marker)
    if problem is not None:
        return _invalid_param(
            source_entity,
            declaration,
            marker=marker,
            rule_id_prefix=f"{rule_id.rsplit('/', 1)[0]}/invalid_declaration",
            problem=problem,
            rule_id_suffix=rule_id_suffix,
        )

    rule = Rule(
        rule_id=with_rule_id_suffix(rule_id, rule_id_suffix),
        rule_type=rule_type,
        name=marker,
        severity=_severity(params_kwargs),
        scope=source_entity.kind,
        evidence_type="runtime",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            **_case_params(params_kwargs),
            "mode": mode,
            "modules": sorted(set(modules or [])),
            "allow": sorted(set(allow or [])),
            **(
                {"transitive": True, "through": sorted(set(through or []))}
                if transitive
                else {}
            ),
            **({"cover_module": True} if cover_module else {}),
        },
        message_template=(
            f"{marker} for " "{target.module_path}:{target.qualname}: {details.summary}"
        ),
        fix_hints=(
            hint,
            "Runs only with --dynamic; without it the rule is SKIPPED.",
        ),
        enabled=True,
    )
    return [rule], [], []


def compile_forbid_runtime_calls(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    return _compile_module_list(
        "forbid_runtime_calls", source_entity, declaration, rule_id_suffix
    )


def compile_require_runtime_calls(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    return _compile_module_list(
        "require_runtime_calls", source_entity, declaration, rule_id_suffix
    )


def compile_forbid_runtime_instantiation(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    return _compile_module_list(
        "forbid_runtime_instantiation", source_entity, declaration, rule_id_suffix
    )


def compile_enforce_reference_calls(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    marker = "enforce_reference_calls"
    params_kwargs = dict(declaration.params)
    if source_entity.kind not in _SUPPORTED_KINDS:
        return _invalid_target(
            source_entity, declaration, marker, sorted(_SUPPORTED_KINDS)
        )
    require_all = params_kwargs.get("require_all", False)
    allow_new_modules = params_kwargs.get("allow_new_modules", False)
    problem: tuple[str, str] | None = None
    if not isinstance(require_all, bool):
        problem = ("require_all", "require_all must be True or False")
    elif not isinstance(allow_new_modules, bool):
        problem = ("allow_new_modules", "allow_new_modules must be True or False")
    else:
        problem = runtime_cases_problem(params_kwargs, source_entity.kind, marker)
    if problem is not None:
        return _invalid_param(
            source_entity,
            declaration,
            marker=marker,
            rule_id_prefix="DYN001/enforce_reference_calls/invalid_declaration",
            problem=problem,
            rule_id_suffix=rule_id_suffix,
        )
    rule = Rule(
        rule_id=with_rule_id_suffix(
            "DYN001/enforce_reference_calls/v1", rule_id_suffix
        ),
        rule_type="runtime_reference_calls",
        name=marker,
        severity=_severity(params_kwargs),
        scope=source_entity.kind,
        evidence_type="runtime",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            **_case_params(params_kwargs),
            "require_all": require_all,
            **({"allow_new_modules": True} if allow_new_modules else {}),
        },
        message_template=(
            "enforce_reference_calls for "
            "{target.module_path}:{target.qualname}: {details.summary}"
        ),
        fix_hints=(
            "Call between modules only where the reference does; move the call "
            "into the layer the reference uses for it.",
            "Runs only with --dynamic; without it the rule is SKIPPED.",
        ),
        enabled=True,
    )
    return [rule], [], []


def _class_rule(
    source_entity: Entity,
    *,
    marker: str,
    rule_id: str,
    rule_type: str,
    params: dict[str, Any],
    severity: Literal["error", "warning", "info"],
    hint: str,
    rule_id_suffix: str,
) -> Rule:
    return Rule(
        rule_id=with_rule_id_suffix(rule_id, rule_id_suffix),
        rule_type=rule_type,
        name=marker,
        severity=severity,
        scope=source_entity.kind,
        evidence_type="runtime",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={**params, "fail_on_unmatched": True},
        message_template=(
            f"{marker} for " "{target.module_path}:{target.qualname}: {details.summary}"
        ),
        fix_hints=(hint, "Runs only with --dynamic; without it the rule is SKIPPED."),
        enabled=True,
    )


_MEMBER_MARKERS = {
    "require_runtime_members": (
        "require",
        "Make sure every instance ends up with the member, however it is created.",
    ),
    "forbid_runtime_members": (
        "forbid",
        "Do not store the member on the object, not even dynamically.",
    ),
}


def _compile_runtime_members(
    marker: str,
    source_entity: Entity,
    declaration: DeclarationEntry,
    rule_id_suffix: str,
) -> Tuple[List[Any], List[Any], List[Any]]:
    mode, hint = _MEMBER_MARKERS[marker]
    params_kwargs = dict(declaration.params)
    if source_entity.kind != "class":
        return _invalid_target(source_entity, declaration, marker, "class")
    names = _module_names(params_kwargs.get("names", []))
    types = params_kwargs.get("types")
    problem: tuple[str, str] | None = None
    if not names or not all(name.isidentifier() for name in names):
        problem = ("names", "give at least one attribute name")
    elif types is not None and mode != "require":
        problem = ("types", f"types does not apply to {marker}")
    elif types is not None and not (
        isinstance(types, dict)
        and all(isinstance(v, str) and v for v in types.values())
    ):
        problem = ("types", "types must map member names to class names")
    elif types is not None and set(types) - set(names):
        unknown = ", ".join(sorted(set(types) - set(names)))
        problem = ("types", f"types names members not listed: {unknown}")
    else:
        problem = runtime_cases_problem(params_kwargs, source_entity.kind, marker)
    if problem is not None:
        return _invalid_param(
            source_entity,
            declaration,
            marker=marker,
            rule_id_prefix=f"DYN005/{marker}/invalid_declaration",
            problem=problem,
            rule_id_suffix=rule_id_suffix,
        )
    rule = _class_rule(
        source_entity,
        marker=marker,
        rule_id=f"DYN005/{marker}/v1",
        rule_type="runtime_members",
        params={
            **_case_params(params_kwargs),
            "mode": mode,
            "names": sorted(set(names or [])),
            **({"types": dict(types)} if types else {}),
        },
        severity=_severity(params_kwargs),
        hint=hint,
        rule_id_suffix=rule_id_suffix,
    )
    return [rule], [], []


def compile_require_runtime_members(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    return _compile_runtime_members(
        "require_runtime_members", source_entity, declaration, rule_id_suffix
    )


def compile_forbid_runtime_members(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    return _compile_runtime_members(
        "forbid_runtime_members", source_entity, declaration, rule_id_suffix
    )


def _timeout_problem(params: dict[str, Any]) -> tuple[str, str] | None:
    timeout_s = params.get("timeout_s", 5.0)
    if (
        isinstance(timeout_s, bool)
        or not isinstance(timeout_s, (int, float))
        or not 0 < timeout_s <= _MAX_TIMEOUT_S
    ):
        return "timeout_s", f"timeout_s must be a number in (0, {_MAX_TIMEOUT_S:g}]"
    return None


def compile_is_runtime_concrete_class(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    marker = "is_runtime_concrete_class"
    params_kwargs = dict(declaration.params)
    if source_entity.kind != "class":
        return _invalid_target(source_entity, declaration, marker, "class")
    problem = runtime_cases_problem(params_kwargs, source_entity.kind, marker)
    if problem is not None:
        return _invalid_param(
            source_entity,
            declaration,
            marker=marker,
            rule_id_prefix=f"DYN006/{marker}/invalid_declaration",
            problem=problem,
            rule_id_suffix=rule_id_suffix,
        )
    rule = _class_rule(
        source_entity,
        marker=marker,
        rule_id=f"DYN006/{marker}/v1",
        rule_type="runtime_class_kind",
        params={**_case_params(params_kwargs), "expect": "concrete"},
        severity=_severity(params_kwargs),
        hint=(
            "Implement every abstract method the class inherits, including those "
            "of bases outside the project."
        ),
        rule_id_suffix=rule_id_suffix,
    )
    return [rule], [], []


def compile_is_runtime_abstract_class(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    marker = "is_runtime_abstract_class"
    params_kwargs = dict(declaration.params)
    if source_entity.kind != "class":
        return _invalid_target(source_entity, declaration, marker, "class")
    problem = _timeout_problem(params_kwargs)
    if "cases" in params_kwargs:
        problem = ("cases", f"{marker} takes no cases: nothing is instantiated")
    if problem is not None:
        return _invalid_param(
            source_entity,
            declaration,
            marker=marker,
            rule_id_prefix=f"DYN006/{marker}/invalid_declaration",
            problem=problem,
            rule_id_suffix=rule_id_suffix,
        )
    rule = _class_rule(
        source_entity,
        marker=marker,
        rule_id=f"DYN006/{marker}/v1",
        rule_type="runtime_class_kind",
        params={
            # One empty case: the class is inspected, never instantiated.
            "cases": [{}],
            "init": None,
            "timeout_s": float(params_kwargs.get("timeout_s", 5.0)),
            "expect": "abstract",
        },
        severity=_severity(params_kwargs),
        hint=(
            "Keep at least one abstract method unimplemented (for example by "
            "deriving from abc.ABC and marking it @abstractmethod)."
        ),
        rule_id_suffix=rule_id_suffix,
    )
    return [rule], [], []


def _required_positional(method: Entity) -> int:
    """Positional arguments a protocol method needs, without ``self``."""
    signature = method.signature
    if signature is None:
        return 0
    required = signature.posonly + signature.pos - signature.defaults
    if method.decorators_meta.get("method_kind") != "static":
        required -= 1
    return max(required, 0)


def compile_implements_runtime_protocol(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    source_entities: list[Entity],
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    from pythonarchtesting.protocols.introspection import (
        protocol_attributes,
        protocol_methods,
    )

    from .protocols import _resolve_protocol_entity

    marker = "implements_runtime_protocol"
    params_kwargs = dict(declaration.params)
    if source_entity.kind != "class":
        return _invalid_target(source_entity, declaration, marker, "class")
    protocol_entity, protocol_ref, evidence = _resolve_protocol_entity(
        source_entity, declaration, source_entities=source_entities
    )
    if protocol_entity is None or protocol_ref is None:
        return [], evidence, []
    problem = runtime_cases_problem(params_kwargs, source_entity.kind, marker)
    if problem is not None:
        return _invalid_param(
            source_entity,
            declaration,
            marker=marker,
            rule_id_prefix=f"DYN007/{marker}/invalid_declaration",
            problem=problem,
            rule_id_suffix=rule_id_suffix,
        )
    methods = {
        method.name: _required_positional(method)
        for method in protocol_methods(protocol_entity, source_entities)
    }
    attributes = sorted(
        attribute.name
        for attribute in protocol_attributes(protocol_entity, source_entities)
        if attribute.name not in methods
    )
    rule = _class_rule(
        source_entity,
        marker=marker,
        rule_id=f"DYN007/{marker}/v1",
        rule_type="runtime_protocol",
        params={
            **_case_params(params_kwargs),
            "protocol": protocol_ref,
            "methods": dict(sorted(methods.items())),
            "attributes": attributes,
        },
        severity=_severity(params_kwargs),
        hint=(
            "Give instances every member of the protocol, with methods that "
            "accept the protocol's arguments."
        ),
        rule_id_suffix=rule_id_suffix,
    )
    return [rule], [], []


def _identifier_problem(
    params: dict[str, Any], key: str, *, required: bool
) -> tuple[str, str] | None:
    value = params.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.isidentifier():
        return key, f"{key} must be a method name"
    return None


def _no_steps_problem(params: dict[str, Any], marker: str) -> tuple[str, str] | None:
    cases = params.get("cases")
    if isinstance(cases, list) and any(
        isinstance(case, dict) and "steps" in case for case in cases
    ):
        return "cases", f"{marker} builds no instance to run steps on"
    return None


def _mentions_spy(value: Any, spy: str) -> bool:
    if isinstance(value, dict):
        if value.get("$spy") == spy:
            return True
        return any(_mentions_spy(item, spy) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_mentions_spy(item, spy) for item in value)
    return False


def _pattern_rule(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    marker: str,
    params: dict[str, Any],
    problem: tuple[str, str] | None,
    hint: str,
    rule_id_suffix: str,
) -> Tuple[List[Any], List[Any], List[Any]]:
    params_kwargs = dict(declaration.params)
    if problem is None:
        problem = runtime_cases_problem(params_kwargs, source_entity.kind, marker)
    if problem is not None:
        return _invalid_param(
            source_entity,
            declaration,
            marker=marker,
            rule_id_prefix=f"DYN008/{marker}/invalid_declaration",
            problem=problem,
            rule_id_suffix=rule_id_suffix,
        )
    rule = _class_rule(
        source_entity,
        marker=marker,
        rule_id=f"DYN008/{marker}/v1",
        rule_type="runtime_pattern",
        params={**_case_params(params_kwargs), **params},
        severity=_severity(params_kwargs),
        hint=hint,
        rule_id_suffix=rule_id_suffix,
    )
    return [rule], [], []


def compile_is_runtime_singleton(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    marker = "is_runtime_singleton"
    if source_entity.kind != "class":
        return _invalid_target(source_entity, declaration, marker, "class")
    params_kwargs = dict(declaration.params)
    return _pattern_rule(
        source_entity,
        declaration,
        marker=marker,
        params={"pattern": "singleton", "access": params_kwargs.get("access")},
        problem=_identifier_problem(params_kwargs, "access", required=False)
        or _no_steps_problem(params_kwargs, marker),
        hint=(
            "Hand out one shared instance: keep it on the class and return it "
            "on every access."
        ),
        rule_id_suffix=rule_id_suffix,
    )


def compile_enforce_runtime_observer(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    marker = "enforce_runtime_observer"
    if source_entity.kind != "class":
        return _invalid_target(source_entity, declaration, marker, "class")
    params_kwargs = dict(declaration.params)
    problem = (
        _identifier_problem(params_kwargs, "subscribe", required=True)
        or _identifier_problem(params_kwargs, "notify", required=True)
        or _identifier_problem(params_kwargs, "unsubscribe", required=False)
    )
    notify_args = params_kwargs.get("notify_args")
    if notify_args is None:
        notify_args = []
    if problem is None and not isinstance(notify_args, list):
        problem = ("notify_args", "notify_args must be a list")
    if problem is None and _transport_problem(notify_args):
        problem = ("notify_args", f"notify_args: {_transport_problem(notify_args)}")
    subscribe_args = params_kwargs.get("subscribe_args")
    if subscribe_args is None:
        subscribe_args = []
    if problem is None and not isinstance(subscribe_args, list):
        problem = ("subscribe_args", "subscribe_args must be a list")
    if problem is None and _transport_problem(subscribe_args):
        problem = (
            "subscribe_args",
            f"subscribe_args: {_transport_problem(subscribe_args)}",
        )
    return _pattern_rule(
        source_entity,
        declaration,
        marker=marker,
        params={
            "pattern": "observer",
            "subscribe": params_kwargs.get("subscribe"),
            "notify": params_kwargs.get("notify"),
            "unsubscribe": params_kwargs.get("unsubscribe"),
            "notify_args": notify_args,
            "subscribe_args": subscribe_args,
        },
        problem=problem,
        hint=(
            "Keep the registered listeners and call each of them when notifying; "
            "forget a listener when it unsubscribes."
        ),
        rule_id_suffix=rule_id_suffix,
    )


def compile_require_runtime_delegation(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    marker = "require_runtime_delegation"
    if source_entity.kind not in _SUPPORTED_KINDS:
        return _invalid_target(
            source_entity, declaration, marker, sorted(_SUPPORTED_KINDS)
        )
    params_kwargs = dict(declaration.params)
    spy = params_kwargs.get("spy")
    problem: tuple[str, str] | None = None
    if not isinstance(spy, str) or not spy:
        problem = ("spy", "give the name of the spy the code must delegate to")
    else:
        problem = _identifier_problem(params_kwargs, "member", required=False)
    if problem is None:
        # Malformed cases are reported as such, not as a missing spy.
        problem = runtime_cases_problem(params_kwargs, source_entity.kind, marker)
    if problem is None and not _mentions_spy(
        [params_kwargs.get("cases"), params_kwargs.get("init")], str(spy)
    ):
        problem = (
            "cases",
            f'no case passes {{"$spy": "{spy}"}}, so nothing can be delegated to it',
        )
    return _pattern_rule(
        source_entity,
        declaration,
        marker=marker,
        params={
            "pattern": "delegation",
            "spy": spy,
            "member": params_kwargs.get("member"),
        },
        problem=problem,
        hint=(
            "Call the injected collaborator for this work instead of doing it "
            "in place."
        ),
        rule_id_suffix=rule_id_suffix,
    )


def compile_forbid_foreign_writes(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    marker = "forbid_foreign_writes"
    params_kwargs = dict(declaration.params)
    if source_entity.kind not in _SUPPORTED_KINDS:
        return _invalid_target(
            source_entity, declaration, marker, sorted(_SUPPORTED_KINDS)
        )
    problem = runtime_cases_problem(params_kwargs, source_entity.kind, marker)
    if problem is not None:
        return _invalid_param(
            source_entity,
            declaration,
            marker=marker,
            rule_id_prefix="DYN003/forbid_foreign_writes/invalid_declaration",
            problem=problem,
            rule_id_suffix=rule_id_suffix,
        )
    rule = Rule(
        rule_id=with_rule_id_suffix("DYN003/forbid_foreign_writes/v1", rule_id_suffix),
        rule_type="runtime_writes",
        name=marker,
        severity=_severity(params_kwargs),
        scope=source_entity.kind,
        evidence_type="runtime",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params=_case_params(params_kwargs),
        message_template=(
            "forbid_foreign_writes for "
            "{target.module_path}:{target.qualname}: {details.summary}"
        ),
        fix_hints=(
            "Ask the object to change itself through one of its methods instead "
            "of assigning its attribute from outside.",
            "Runs only with --dynamic; without it the rule is SKIPPED.",
        ),
        enabled=True,
    )
    return [rule], [], []


def compile_forbid_runtime_imports(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    params_kwargs = dict(declaration.params)

    if source_entity.kind != "module":
        return _invalid_target(
            source_entity, declaration, "forbid_runtime_imports", "module"
        )

    forbidden = _module_names(params_kwargs.get("forbidden", []))
    allow = _module_names(params_kwargs.get("allow") or [])
    timeout_s = params_kwargs.get("timeout_s", 5.0)
    problem: tuple[str, str] | None = None
    if not forbidden:
        problem = ("forbidden", "give at least one module name to forbid")
    elif allow is None:
        problem = ("allow", "allow must be a list of module names")
    elif (
        isinstance(timeout_s, bool)
        or not isinstance(timeout_s, (int, float))
        or not 0 < timeout_s <= _MAX_TIMEOUT_S
    ):
        problem = (
            "timeout_s",
            f"timeout_s must be a number in (0, {_MAX_TIMEOUT_S:g}]",
        )
    if problem is not None:
        return _invalid_param(
            source_entity,
            declaration,
            marker="forbid_runtime_imports",
            rule_id_prefix="DYN002/forbid_runtime_imports/invalid_declaration",
            problem=problem,
            rule_id_suffix=rule_id_suffix,
        )

    rule = Rule(
        rule_id=with_rule_id_suffix("DYN002/forbid_runtime_imports/v1", rule_id_suffix),
        rule_type="runtime_imports",
        name="forbid_runtime_imports",
        severity=_severity(params_kwargs),
        scope=source_entity.kind,
        evidence_type="runtime",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            "forbidden": sorted(set(forbidden or [])),
            "allow": sorted(set(allow or [])),
            "timeout_s": float(timeout_s),
            "fail_on_unmatched": True,
        },
        message_template=(
            "forbid_runtime_imports for {target.module_path}: {details.summary}"
        ),
        fix_hints=(
            "Remove the import or move the dependency behind the allowed boundary.",
            "Runs only with --dynamic; without it the rule is SKIPPED.",
        ),
        enabled=True,
    )
    return [rule], [], []


__all__ = [
    "compile_enforce_reference_calls",
    "compile_enforce_runtime_observer",
    "compile_is_runtime_singleton",
    "compile_require_runtime_delegation",
    "compile_forbid_runtime_members",
    "compile_implements_runtime_protocol",
    "compile_is_runtime_abstract_class",
    "compile_is_runtime_concrete_class",
    "compile_require_runtime_members",
    "compile_forbid_foreign_writes",
    "compile_forbid_runtime_calls",
    "compile_forbid_runtime_imports",
    "compile_forbid_runtime_instantiation",
    "compile_require_runtime_calls",
    "runtime_cases_problem",
]
