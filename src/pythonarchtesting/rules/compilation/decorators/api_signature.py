from __future__ import annotations

import re
from typing import Any, List, Literal, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    declaration_evidence,
    invalid_declaration_evidence,
    invalid_target_evidence,
    marker_severity,
    with_rule_id_suffix,
)

_VALID_RETURN_ANNOTATION = {"off", "ignore", "warning", "error"}


def compile_required_entity_signature(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    """
    Compile required entity signature rules from annotation declarations.

    This compiler emits:
    - one required signature compatibility rule (always)
    - optional return annotation rule when configured as warning/error
    """
    from pythonarchtesting.core.models import Rule, RuleSelector

    _ = cfg
    params_kwargs = dict(declaration.params)
    compiler_evidence: List[Evidence] = []

    mode = str(params_kwargs.get("mode", "compatible")).lower()
    if mode not in {"compatible", "exact", "any"}:
        mode = "compatible"

    allow_extra_params = bool(params_kwargs.get("allow_extra_params", True))
    allow_param_rename = bool(params_kwargs.get("allow_param_rename", False))

    return_annotation_raw = str(
        params_kwargs.get("return_annotation", "warning")
    ).lower()
    if return_annotation_raw not in _VALID_RETURN_ANNOTATION:
        return_annotation_payload: dict[str, Any] = {
            "decorator": "required_entity_signature",
            "issue": "compiler_invalid_param",
            "param": "return_annotation",
            "value": return_annotation_raw,
            "valid": sorted(_VALID_RETURN_ANNOTATION),
        }
        compiler_evidence.append(
            declaration_evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_param",
                payload=return_annotation_payload,
            )
        )
        return [], compiler_evidence, []

    # "ignore" is an alias for "off" — both suppress the return-only sibling rule.
    return_annotation = (
        "off" if return_annotation_raw == "ignore" else return_annotation_raw
    )

    base_severity = marker_severity(params_kwargs)

    selector = RuleSelector(
        source_entity_id=source_entity.canonical_id,
        explicit_target=None,
    )

    shared_params = {
        "mode": mode,
        "allow_extra_params": allow_extra_params,
        "allow_param_rename": allow_param_rename,
    }

    rules = [
        Rule(
            rule_id=with_rule_id_suffix(
                "API001/required_entity_signature/v1", rule_id_suffix
            ),
            rule_type="api_signature",
            name="required_entity_signature",
            severity=base_severity,
            scope=source_entity.kind,
            evidence_type="static",
            selector=selector,
            params={
                **shared_params,
                "check_return": False,
                "fail_on_unmatched": True,
            },
            message_template=(
                "Required signature mismatch for {target.module_path}:{target.qualname}: "
                "{details.reason}"
            ),
            fix_hints=(
                "Match the required parameter names, kinds, and required/optional shape.",
            ),
            enabled=True,
        )
    ]

    if return_annotation != "off":
        return_rule_severity: Literal["error", "warning"] = (
            "error" if return_annotation == "error" else "warning"
        )
        rules.append(
            Rule(
                rule_id=with_rule_id_suffix(
                    "API001/required_entity_signature_return/v1",
                    rule_id_suffix,
                ),
                rule_type="api_signature",
                name="required_entity_signature_return",
                severity=return_rule_severity,
                scope=source_entity.kind,
                evidence_type="static",
                selector=selector,
                params={
                    **shared_params,
                    "check_return": True,
                    "return_only": True,
                    "fail_on_unmatched": False,
                },
                message_template=(
                    "Required return annotation mismatch for "
                    "{target.module_path}:{target.qualname}: {details.reason}"
                ),
                fix_hints=("Match the required return annotation.",),
                enabled=True,
            )
        )

    return rules, compiler_evidence, []


def compile_required_method(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    """
    Compile required method rules from annotation declarations.

    This compiler emits a single API002 rule and records compiler evidence when
    the declaration is used on a non-method entity.
    """
    from pythonarchtesting.core.models import Rule, RuleSelector

    _ = cfg
    params_kwargs = dict(declaration.params)
    compiler_evidence: List[Evidence] = []

    mode = str(params_kwargs.get("signature_mode", "compatible")).lower()
    if mode not in {"compatible", "exact", "any"}:
        mode = "compatible"

    enforce_method_kind = bool(params_kwargs.get("enforce_method_kind", True))
    allow_missing = bool(params_kwargs.get("allow_missing", False))
    declared_only = bool(params_kwargs.get("declared_only", False))
    name_match = str(params_kwargs.get("name_match", "exact")).lower()
    aliases_raw = params_kwargs.get("aliases")
    pattern = params_kwargs.get("pattern")

    base_severity = marker_severity(params_kwargs)

    if source_entity.kind != "method":
        compiler_evidence.append(
            invalid_target_evidence(
                source_entity,
                declaration,
                decorator="required_method",
                expected_kind="method",
            )
        )
        return [], compiler_evidence, []

    if name_match not in {"exact", "alias", "regex", "any"}:
        compiler_evidence.append(
            invalid_declaration_evidence(
                source_entity,
                declaration,
                decorator="required_method",
                reason="name_match must be one of: exact, alias, regex, any",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    aliases: list[str] | None = None
    if aliases_raw is not None:
        if not isinstance(aliases_raw, list):
            compiler_evidence.append(
                invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    decorator="required_method",
                    reason="aliases must be a list of non-empty strings",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
        aliases = [str(alias) for alias in aliases_raw]
        if any(not alias.strip() for alias in aliases):
            compiler_evidence.append(
                invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    decorator="required_method",
                    reason="aliases must contain only non-empty strings",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []

    if pattern is not None and not isinstance(pattern, str):
        compiler_evidence.append(
            invalid_declaration_evidence(
                source_entity,
                declaration,
                decorator="required_method",
                reason="pattern must be a non-empty string",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    if name_match == "exact":
        if aliases not in (None, []) or pattern is not None:
            compiler_evidence.append(
                invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    decorator="required_method",
                    reason="exact name matching does not accept aliases or pattern",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
    elif name_match == "alias":
        if not aliases:
            compiler_evidence.append(
                invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    decorator="required_method",
                    reason="alias name matching requires a non-empty aliases list",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
        if pattern is not None:
            compiler_evidence.append(
                invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    decorator="required_method",
                    reason="alias name matching does not accept pattern",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
    elif name_match == "regex":
        if aliases not in (None, []):
            compiler_evidence.append(
                invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    decorator="required_method",
                    reason="regex name matching does not accept aliases",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
        if not isinstance(pattern, str) or not pattern.strip():
            compiler_evidence.append(
                invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    decorator="required_method",
                    reason="regex name matching requires a non-empty pattern",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
        try:
            re.compile(pattern)
        except re.error as exc:
            compiler_evidence.append(
                invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    decorator="required_method",
                    reason=f"invalid regex pattern: {exc}",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
    elif name_match == "any" and (aliases not in (None, []) or pattern is not None):
        compiler_evidence.append(
            invalid_declaration_evidence(
                source_entity,
                declaration,
                decorator="required_method",
                reason="any name matching does not accept aliases or pattern",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    selector = RuleSelector(
        source_entity_id=source_entity.canonical_id,
        explicit_target=None,
    )

    rule = Rule(
        rule_id=with_rule_id_suffix("API002/required_method/v1", rule_id_suffix),
        rule_type="api_signature",
        name="required_method",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=selector,
        params={
            "mode": mode,
            "allow_extra_params": True,
            "allow_param_rename": False,
            "check_return": False,
            "allow_missing": allow_missing,
            "fail_on_unmatched": not allow_missing,
            "enforce_method_kind": enforce_method_kind,
            "declared_only": declared_only,
            "name_match": name_match,
            "aliases": aliases,
            "pattern": pattern,
        },
        message_template=(
            "Required method mismatch for {target.module_path}:{target.qualname}: "
            "{details.reason}"
        ),
        fix_hints=(
            "Implement the required method with compatible parameters.",
            "Match required method kind (instance/class/static).",
        ),
        enabled=True,
    )

    return [rule], compiler_evidence, []


__all__ = ["compile_required_entity_signature", "compile_required_method"]
