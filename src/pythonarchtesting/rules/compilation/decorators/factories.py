from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    build_invalid_param_sentinel_rule,
    canonicalize_payload,
    evidence_id,
    with_rule_id_suffix,
)

_VALID_SATISFY_WITH = frozenset(
    {"constructor", "classmethod", "staticmethod", "static_attribute"}
)
_VALID_NAME_MATCH = frozenset({"any", "exact", "alias", "regex"})
_VALID_RETURN_ANNOTATION_MODE = frozenset({"ignore", "compatible", "exact"})
_VALID_DETECTION_MODE = frozenset({"strict", "extended"})
_VALID_SIGNATURE_MODES = frozenset({"compatible", "exact", "any"})
_FACTORY_METHOD_NAMES = frozenset({"__init__", "__new__"})


def _is_factory_capable_method(entity: Entity) -> bool:
    if entity.kind != "method":
        return False
    if entity.name in _FACTORY_METHOD_NAMES:
        return True
    method_kind = entity.surface_meta.get("method_kind")
    return method_kind in {"class", "static"}


def _bool_param(
    params: dict[str, Any], name: str, *, default: bool
) -> tuple[bool, bool]:
    value = params.get(name, default)
    if isinstance(value, bool):
        return value, True
    return default, False


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
        rule_id_prefix="API004/required_factory/invalid_param",
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
    params_kwargs = dict(declaration.params)
    compiler_evidence: List[Evidence] = []

    location = {
        "filepath": source_entity.filepath_rel,
        "lineno": declaration.lineno or source_entity.lineno,
        "col": declaration.col,
    }

    if source_entity.kind != "method":
        payload = {
            "decorator": "required_factory",
            "issue": "compiler_invalid_target",
            "expected_kind": "method",
            "found_kind": source_entity.kind,
        }
        compiler_evidence.append(
            Evidence(
                evidence_id=evidence_id("compiler_invalid_target", payload),
                type="compiler_invalid_target",
                source="compiler",
                role="source",
                entity_id=source_entity.canonical_id,
                payload=canonicalize_payload(payload),
                location=location,
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
            Evidence(
                evidence_id=evidence_id("compiler_invalid_source_method", payload),
                type="compiler_invalid_source_method",
                source="compiler",
                role="source",
                entity_id=source_entity.canonical_id,
                payload=canonicalize_payload(payload),
                location=location,
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
            Evidence(
                evidence_id=evidence_id(
                    "compiler_invalid_param", signature_mode_payload
                ),
                type="compiler_invalid_param",
                source="compiler",
                role="source",
                entity_id=source_entity.canonical_id,
                payload=canonicalize_payload(signature_mode_payload),
                location=location,
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
            Evidence(
                evidence_id=evidence_id(
                    "compiler_invalid_param", invalid_param_payload
                ),
                type="compiler_invalid_param",
                source="compiler",
                role="source",
                entity_id=source_entity.canonical_id,
                payload=canonicalize_payload(invalid_param_payload),
                location=location,
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

    allow_inherited = bool(params_kwargs.get("allow_inherited", True))
    allow_missing, allow_missing_valid = _bool_param(
        params_kwargs,
        "allow_missing",
        default=False,
    )
    if not allow_missing_valid:
        payload = {
            "decorator": "required_factory",
            "issue": "compiler_invalid_param",
            "param": "allow_missing",
            "reason": "allow_missing must be a boolean",
        }
        compiler_evidence.append(
            Evidence(
                evidence_id=evidence_id("compiler_invalid_param", payload),
                type="compiler_invalid_param",
                source="compiler",
                role="source",
                entity_id=source_entity.canonical_id,
                payload=canonicalize_payload(payload),
                location=location,
            )
        )
        sentinel = _invalid_param_sentinel_rule(
            source_entity,
            param="allow_missing",
            value=params_kwargs.get("allow_missing"),
            reason="allow_missing must be a boolean",
            rule_id_suffix=rule_id_suffix,
        )
        return [sentinel], compiler_evidence, []
    name_match = str(params_kwargs.get("name_match", "any")).lower()
    if name_match not in _VALID_NAME_MATCH:
        name_match = "any"

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
            Evidence(
                evidence_id=evidence_id(
                    "compiler_invalid_param", return_annotation_payload
                ),
                type="compiler_invalid_param",
                source="compiler",
                role="source",
                entity_id=source_entity.canonical_id,
                payload=canonicalize_payload(return_annotation_payload),
                location=location,
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
        "extended"
        if source_entity.extras.get("assignment_wrapped_by")
        else "strict"
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
            Evidence(
                evidence_id=evidence_id(
                    "compiler_invalid_param", detection_mode_payload
                ),
                type="compiler_invalid_param",
                source="compiler",
                role="source",
                entity_id=source_entity.canonical_id,
                payload=canonicalize_payload(detection_mode_payload),
                location=location,
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
            Evidence(
                evidence_id=evidence_id("compiler_invalid_param", payload),
                type="compiler_invalid_param",
                source="compiler",
                role="source",
                entity_id=source_entity.canonical_id,
                payload=canonicalize_payload(payload),
                location=location,
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
            Evidence(
                evidence_id=evidence_id("compiler_invalid_param", payload),
                type="compiler_invalid_param",
                source="compiler",
                role="source",
                entity_id=source_entity.canonical_id,
                payload=canonicalize_payload(payload),
                location=location,
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
        payload = {
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
            Evidence(
                evidence_id=evidence_id("compiler_invalid_param", payload),
                type="compiler_invalid_param",
                source="compiler",
                role="source",
                entity_id=source_entity.canonical_id,
                payload=canonicalize_payload(payload),
                location=location,
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

    base_severity_raw = str(
        params_kwargs.get("severity", "error")
    ).lower()  # noqa: E501
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

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
