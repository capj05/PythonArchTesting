from __future__ import annotations

from typing import Any, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    bool_param,
    build_invalid_param_sentinel_rule,
    declaration_evidence,
    invalid_target_evidence,
    marker_severity,
    options_problem,
    reject_invalid_param,
    reject_invalid_severity,
    with_rule_id_suffix,
    without_none,
)

_VALID_SATISFY_WITH = frozenset(
    {"constructor", "classmethod", "staticmethod", "static_attribute"}
)
_VALID_NAME_MATCH = frozenset({"any", "exact", "alias", "regex"})
_VALID_RETURN_ANNOTATION_MODE = frozenset({"ignore", "compatible", "exact"})
_VALID_DETECTION_MODE = frozenset({"strict", "extended"})
_VALID_SIGNATURE_MODES = frozenset({"compatible", "exact", "any"})
_FACTORY_METHOD_NAMES = frozenset({"__init__", "__new__"})
_BOOLS = ("allow_inherited", "allow_missing")
_OPTIONS = (
    "signature_mode",
    "satisfy_with",
    "name_match",
    "return_annotation_mode",
    "detection_mode",
    *_BOOLS,
)
_INVALID_PREFIX = "API004/required_factory/invalid_param"


def _is_factory_capable_method(entity: Entity) -> bool:
    if entity.kind != "method":
        return False
    if entity.name in _FACTORY_METHOD_NAMES:
        return True
    method_kind = entity.surface_meta.get("method_kind")
    return method_kind in {"class", "static"}


def _invalid_param_sentinel_rule(
    source_entity: Entity,
    *,
    param: str,
    value: Any = None,
    valid: list[str] | None = None,
    reason: str | None = None,
    rule_id_suffix: str,
) -> Any:
    """Build a sentinel Rule that surfaces a dropped required_factory rule.

    Thin delegator over :func:`build_invalid_param_sentinel_rule`.
    """
    return build_invalid_param_sentinel_rule(
        source_entity,
        decorator_name="required_factory",
        rule_id_prefix=_INVALID_PREFIX,
        param=param,
        value=value,
        valid=valid,
        reason=reason,
        rule_id_suffix=rule_id_suffix,
    )


def compile_required_factory(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compile required_factory declarations into API004 signature rules."""
    from pythonarchtesting.core.models import Rule, RuleSelector

    _ = cfg
    params_kwargs = without_none(declaration.params, _OPTIONS)
    compiler_evidence: List[Evidence] = []

    if source_entity.kind != "method":
        compiler_evidence.append(
            invalid_target_evidence(
                source_entity,
                declaration,
                decorator="required_factory",
                expected_kind="method",
            )
        )
        return [], compiler_evidence, []

    if not _is_factory_capable_method(source_entity):
        payload = {
            "decorator": "required_factory",
            "issue": "compiler_invalid_source_method",
            "reason": "plain instance methods are not valid factory sources in v1",
            "entity_name": source_entity.name,
        }
        compiler_evidence.append(
            declaration_evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_source_method",
                payload=payload,
            )
        )
        return [], compiler_evidence, []

    signature_mode = str(params_kwargs.get("signature_mode", "compatible")).lower()
    if signature_mode not in _VALID_SIGNATURE_MODES:
        signature_mode_payload: dict[str, Any] = {
            "decorator": "required_factory",
            "issue": "compiler_invalid_param",
            "param": "signature_mode",
            "value": signature_mode,
            "valid": sorted(_VALID_SIGNATURE_MODES),
        }
        compiler_evidence.append(
            declaration_evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_param",
                payload=signature_mode_payload,
            )
        )
        sentinel = _invalid_param_sentinel_rule(
            source_entity,
            param="signature_mode",
            value=signature_mode,
            valid=sorted(_VALID_SIGNATURE_MODES),
            rule_id_suffix=rule_id_suffix,
        )
        return [sentinel], compiler_evidence, []

    caller_constrained_name = (
        params_kwargs.get("aliases") is not None
        or params_kwargs.get("pattern") is not None
        or str(params_kwargs.get("name_match", "any")).lower() != "any"
    )
    default_satisfy_with: list[str] = (
        ["classmethod", "staticmethod"]
        if caller_constrained_name
        else ["constructor", "classmethod", "staticmethod"]
    )
    satisfy_with_raw = params_kwargs.get("satisfy_with", default_satisfy_with)
    satisfy_with = [str(value) for value in satisfy_with_raw]
    invalid_satisfy = [
        value for value in satisfy_with if value not in _VALID_SATISFY_WITH
    ]
    if invalid_satisfy or not satisfy_with:
        invalid_param_payload: dict[str, Any] = {
            "decorator": "required_factory",
            "issue": "compiler_invalid_param",
            "param": "satisfy_with",
            "value": satisfy_with,
            "valid": sorted(_VALID_SATISFY_WITH),
        }
        compiler_evidence.append(
            declaration_evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_param",
                payload=invalid_param_payload,
            )
        )
        sentinel = _invalid_param_sentinel_rule(
            source_entity,
            param="satisfy_with",
            value=satisfy_with,
            valid=sorted(_VALID_SATISFY_WITH),
            rule_id_suffix=rule_id_suffix,
        )
        return [sentinel], compiler_evidence, []

    rejected = reject_invalid_param(
        source_entity,
        declaration,
        options_problem(
            params_kwargs, bools=_BOOLS, choices={"name_match": _VALID_NAME_MATCH}
        ),
        marker="required_factory",
        rule_id_prefix=_INVALID_PREFIX,
        rule_id_suffix=rule_id_suffix,
    )
    if rejected is not None:
        return rejected
    allow_inherited = bool_param(params_kwargs, "allow_inherited", default=True)
    allow_missing = bool_param(params_kwargs, "allow_missing", default=False)
    name_match = str(params_kwargs.get("name_match", "any")).lower()

    aliases = params_kwargs.get("aliases")
    pattern = params_kwargs.get("pattern")
    return_annotation_mode = str(
        params_kwargs.get("return_annotation_mode", "ignore")
    ).lower()
    if return_annotation_mode not in _VALID_RETURN_ANNOTATION_MODE:
        return_annotation_payload: dict[str, Any] = {
            "decorator": "required_factory",
            "issue": "compiler_invalid_param",
            "param": "return_annotation_mode",
            "value": return_annotation_mode,
            "valid": sorted(_VALID_RETURN_ANNOTATION_MODE),
        }
        compiler_evidence.append(
            declaration_evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_param",
                payload=return_annotation_payload,
            )
        )
        sentinel = _invalid_param_sentinel_rule(
            source_entity,
            param="return_annotation_mode",
            value=return_annotation_mode,
            valid=sorted(_VALID_RETURN_ANNOTATION_MODE),
            rule_id_suffix=rule_id_suffix,
        )
        return [sentinel], compiler_evidence, []

    default_detection_mode = (
        "extended" if source_entity.extras.get("assignment_wrapped_by") else "strict"
    )
    detection_mode = str(
        params_kwargs.get("detection_mode", default_detection_mode)
    ).lower()
    if detection_mode not in _VALID_DETECTION_MODE:
        detection_mode_payload: dict[str, Any] = {
            "decorator": "required_factory",
            "issue": "compiler_invalid_param",
            "param": "detection_mode",
            "value": detection_mode,
            "valid": sorted(_VALID_DETECTION_MODE),
        }
        compiler_evidence.append(
            declaration_evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_param",
                payload=detection_mode_payload,
            )
        )
        sentinel = _invalid_param_sentinel_rule(
            source_entity,
            param="detection_mode",
            value=detection_mode,
            valid=sorted(_VALID_DETECTION_MODE),
            rule_id_suffix=rule_id_suffix,
        )
        return [sentinel], compiler_evidence, []

    if name_match == "alias" and not aliases:
        payload = {
            "decorator": "required_factory",
            "issue": "compiler_invalid_param",
            "param": "aliases",
            "reason": "name_match='alias' requires non-empty aliases list",
        }
        compiler_evidence.append(
            declaration_evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_param",
                payload=payload,
            )
        )
        sentinel = _invalid_param_sentinel_rule(
            source_entity,
            param="aliases",
            value=aliases,
            reason="name_match='alias' requires non-empty aliases list",
            rule_id_suffix=rule_id_suffix,
        )
        return [sentinel], compiler_evidence, []

    if name_match == "regex" and not pattern:
        payload = {
            "decorator": "required_factory",
            "issue": "compiler_invalid_param",
            "param": "pattern",
            "reason": "name_match='regex' requires a pattern",
        }
        compiler_evidence.append(
            declaration_evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_param",
                payload=payload,
            )
        )
        sentinel = _invalid_param_sentinel_rule(
            source_entity,
            param="pattern",
            value=pattern,
            reason="name_match='regex' requires a pattern",
            rule_id_suffix=rule_id_suffix,
        )
        return [sentinel], compiler_evidence, []

    if "static_attribute" in satisfy_with and name_match == "any":
        name_match_payload: dict[str, Any] = {
            "decorator": "required_factory",
            "issue": "compiler_invalid_param",
            "param": "name_match",
            "value": "any",
            "reason": (
                "static_attribute factory satisfaction requires constrained "
                "name matching: exact, alias, or regex"
            ),
            "valid": ["exact", "alias", "regex"],
        }
        compiler_evidence.append(
            declaration_evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_param",
                payload=name_match_payload,
            )
        )
        sentinel = _invalid_param_sentinel_rule(
            source_entity,
            param="name_match",
            value="any",
            valid=["exact", "alias", "regex"],
            reason=(
                "static_attribute factory satisfaction requires constrained "
                "name matching: exact, alias, or regex"
            ),
            rule_id_suffix=rule_id_suffix,
        )
        return [sentinel], compiler_evidence, []

    rejected = reject_invalid_severity(
        source_entity,
        declaration,
        marker="required_factory",
        rule_id_prefix=_INVALID_PREFIX,
        rule_id_suffix=rule_id_suffix,
        compiler_evidence=compiler_evidence,
    )
    if rejected is not None:
        return rejected

    base_severity = marker_severity(params_kwargs)

    selector = RuleSelector(
        source_entity_id=source_entity.canonical_id,
        explicit_target=None,
    )

    rule_params: dict[str, Any] = {
        "mode": signature_mode,
        "satisfy_with": satisfy_with,
        "allow_inherited": allow_inherited,
        "allow_missing": allow_missing,
        "name_match": name_match,
        "fail_on_unmatched": not allow_missing,
        "check_return": return_annotation_mode != "ignore",
        "return_annotation_mode": return_annotation_mode,
        "detection_mode": detection_mode,
    }
    if aliases is not None:
        rule_params["aliases"] = list(aliases)
    if pattern is not None:
        rule_params["pattern"] = str(pattern)

    if "static_attribute" in satisfy_with:
        rule_version = "v3"
    elif return_annotation_mode != "ignore" or detection_mode != "strict":
        rule_version = "v2"
    else:
        rule_version = "v1"
    rule = Rule(
        rule_id=with_rule_id_suffix(
            f"API004/required_factory/{rule_version}",
            rule_id_suffix,
        ),
        rule_type="api_signature",
        name="required_factory",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=selector,
        params=rule_params,
        message_template=(
            "Required factory mismatch for {target.module_path}:{target.qualname}: "
            "{details.reason}"
        ),
        fix_hints=(
            "Implement the required factory (constructor, classmethod, or staticmethod).",
            "Match the required factory signature.",
        ),
        enabled=True,
    )

    return [rule], compiler_evidence, []


__all__ = ["compile_required_factory"]
