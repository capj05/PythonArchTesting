from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    bool_param,
    bool_problem,
    choice_problem,
    declaration_evidence,
    marker_severity,
    reject_invalid_param,
    reject_invalid_severity,
    with_rule_id_suffix,
    without_none,
)

_VALID_IMPORT_POLICY_MODES = {"reachable", "direct"}
# "entity" is the legacy name of "module".
_VALID_SCOPES = ("package", "module", "entity")
_OPTIONS = ("scope", "mode", "ignore_type_checking")
_INVALID_PREFIX = "DEP001/forbid_imports/invalid_declaration"


def _normalize_import_policy_scope(raw_scope: Any) -> Literal["module", "package"]:
    """The scope of a declaration whose ``scope`` is valid, in any case."""
    scope = str(raw_scope).lower()
    if scope == "entity":
        return "module"
    return cast(Literal["module", "package"], scope)


def _invalid_mode_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    mode: Any,
) -> Evidence:
    payload = {
        "declaration": "forbid_imports",
        "issue": "invalid_mode",
        "mode": mode,
        "allowed_values": sorted(_VALID_IMPORT_POLICY_MODES),
        "message": "forbid_imports mode must be 'reachable' or 'direct'.",
        "severity": "error",
    }
    return declaration_evidence(
        source_entity,
        declaration,
        evidence_type="compiler_invalid_import_policy_mode",
        payload=payload,
    )


def compile_forbid_imports(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compile forbidden imports policy rules from annotation declarations."""
    from pythonarchtesting.core.models import Rule, RuleSelector

    _ = cfg
    compiler_evidence: List[Evidence] = []
    params_kwargs = without_none(declaration.params, _OPTIONS)

    forbidden_raw = params_kwargs.get("forbidden", [])
    if isinstance(forbidden_raw, str):
        forbidden = [forbidden_raw]
    elif isinstance(forbidden_raw, (list, tuple)):
        forbidden = [str(item) for item in forbidden_raw if isinstance(item, str)]
    else:
        forbidden = []

    allow_raw = params_kwargs.get("allow", [])
    if isinstance(allow_raw, str):
        allow = [allow_raw]
    elif isinstance(allow_raw, (list, tuple)):
        allow = [str(item) for item in allow_raw if isinstance(item, str)]
    else:
        allow = []

    ignore_globs_raw = params_kwargs.get("ignore_globs", [])
    if isinstance(ignore_globs_raw, str):
        ignore_globs = [ignore_globs_raw]
    elif isinstance(ignore_globs_raw, (list, tuple)):
        ignore_globs = [str(item) for item in ignore_globs_raw if isinstance(item, str)]
    else:
        ignore_globs = []

    rejected = reject_invalid_param(
        source_entity,
        declaration,
        choice_problem(params_kwargs, "scope", _VALID_SCOPES),
        marker="forbid_imports",
        rule_id_prefix=_INVALID_PREFIX,
        rule_id_suffix=rule_id_suffix,
        key="declaration",
    )
    if rejected is not None:
        return rejected
    scope = _normalize_import_policy_scope(params_kwargs.get("scope", "package"))

    package = params_kwargs.get("package")
    if package is not None and not isinstance(package, str):
        package = None

    mode = params_kwargs.get("mode", "reachable")
    if not isinstance(mode, str) or mode not in _VALID_IMPORT_POLICY_MODES:
        compiler_evidence.append(
            _invalid_mode_evidence(source_entity, declaration, mode)
        )
        return [], compiler_evidence, []

    reject: dict[str, Any] = {
        "marker": "forbid_imports",
        "rule_id_prefix": _INVALID_PREFIX,
        "rule_id_suffix": rule_id_suffix,
        "key": "declaration",
        "compiler_evidence": compiler_evidence,
    }
    rejected = reject_invalid_param(
        source_entity,
        declaration,
        bool_problem(params_kwargs, "ignore_type_checking"),
        **reject,
    ) or reject_invalid_severity(source_entity, declaration, **reject)
    if rejected is not None:
        return rejected
    ignore_type_checking = bool_param(
        params_kwargs, "ignore_type_checking", default=True
    )

    base_severity = marker_severity(params_kwargs)

    selector = RuleSelector(
        source_entity_id=source_entity.canonical_id,
        explicit_target=None,
    )

    rule = Rule(
        rule_id=with_rule_id_suffix("DEP001/forbid_imports/v2", rule_id_suffix),
        rule_type="import_policy",
        name="forbid_imports",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=selector,
        params={
            "forbidden": sorted(set(forbidden)),
            "scope": scope,
            "package": package,
            "mode": mode,
            "ignore_type_checking": ignore_type_checking,
            "allow": sorted(set(allow)),
            "ignore_globs": sorted(set(ignore_globs)),
            "fail_on_unmatched": False,
        },
        message_template=(
            "DEP001 forbidden imports found in {details.scope} "
            "'{details.scope_value}': {details.forbidden_modules}"
        ),
        fix_hints=(
            "Remove or replace imports that violate the forbidden dependency policy.",
        ),
        enabled=True,
    )

    return [rule], compiler_evidence, []


__all__ = ["compile_forbid_imports"]
