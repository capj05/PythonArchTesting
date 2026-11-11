from __future__ import annotations

import re
from typing import Any, List, Literal, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    bool_param,
    declaration_evidence,
    drop_with_sentinel,
    invalid_declaration_evidence,
    invalid_target_evidence,
    marker_severity,
    options_problem,
    reject_invalid_param,
    reject_invalid_severity,
    reject_misplaced,
    with_rule_id_suffix,
    without_none,
)

_VALID_RETURN_ANNOTATION = {"off", "ignore", "warning", "error"}
_SIGNATURE_MODES = ("compatible", "exact", "any")
_SIGNATURE_BOOLS = ("allow_extra_params", "allow_param_rename")
_SIGNATURE_OPTIONS = ("mode", "return_annotation", *_SIGNATURE_BOOLS)
_METHOD_BOOLS = ("enforce_method_kind", "allow_missing", "declared_only")
_METHOD_OPTIONS = ("signature_mode", "name_match", *_METHOD_BOOLS)
_NAME_MATCHES = ("exact", "alias", "regex", "any")


def _has_aliases(aliases: Any) -> bool:
    return aliases not in (None, [])


def _name_match_problem(
    name_match: str, aliases: Any, pattern: Any
) -> tuple[str, str] | None:
    """The argument at fault and why, when ``name_match`` (lower case),
    ``aliases`` and ``pattern`` of a required_method do not fit together;
    ``None`` when they do. Checked in a fixed order."""
    if name_match not in _NAME_MATCHES:
        return "name_match", "name_match must be one of: exact, alias, regex, any"
    if aliases is not None:
        if not isinstance(aliases, list):
            return "aliases", "aliases must be a list of non-empty strings"
        if any(not str(alias).strip() for alias in aliases):
            return "aliases", "aliases must contain only non-empty strings"
    if pattern is not None and not isinstance(pattern, str):
        return "pattern", "pattern must be a non-empty string"
    if name_match in ("exact", "any"):
        if _has_aliases(aliases) or pattern is not None:
            extra = "aliases" if _has_aliases(aliases) else "pattern"
            return (
                extra,
                f"{name_match} name matching does not accept aliases or pattern",
            )
        return None
    if name_match == "alias":
        if not aliases:
            return "aliases", "alias name matching requires a non-empty aliases list"
        if pattern is not None:
            return "pattern", "alias name matching does not accept pattern"
        return None
    if _has_aliases(aliases):
        return "aliases", "regex name matching does not accept aliases"
    if not isinstance(pattern, str) or not pattern.strip():
        return "pattern", "regex name matching requires a non-empty pattern"
    try:
        # The evaluator strips the pattern, so the stripped one is checked.
        re.compile(pattern.strip())
    except re.error as exc:
        return "pattern", f"invalid regex pattern: {exc}"
    return None


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
    params_kwargs = without_none(declaration.params, _SIGNATURE_OPTIONS)
    compiler_evidence: List[Evidence] = []

    rejected = reject_invalid_param(
        source_entity,
        declaration,
        options_problem(
            params_kwargs, choices={"mode": _SIGNATURE_MODES}, bools=_SIGNATURE_BOOLS
        ),
        marker="required_entity_signature",
        rule_id_prefix="API001/required_entity_signature/invalid_declaration",
        rule_id_suffix=rule_id_suffix,
    )
    if rejected is not None:
        return rejected

    mode = str(params_kwargs.get("mode", "compatible")).lower()
    allow_extra_params = bool_param(params_kwargs, "allow_extra_params", default=True)
    allow_param_rename = bool_param(params_kwargs, "allow_param_rename", default=False)

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
        return drop_with_sentinel(
            source_entity,
            compiler_evidence,
            marker="required_entity_signature",
            rule_id_prefix="API001/required_entity_signature/invalid_declaration",
            rule_id_suffix=rule_id_suffix,
            param="return_annotation",
            value=return_annotation_raw,
            valid=_VALID_RETURN_ANNOTATION,
            reason="return_annotation must be one of: "
            + ", ".join(sorted(_VALID_RETURN_ANNOTATION)),
        )

    # "ignore" is an alias for "off" — both suppress the return-only sibling rule.
    return_annotation = (
        "off" if return_annotation_raw == "ignore" else return_annotation_raw
    )

    rejected = reject_invalid_severity(
        source_entity,
        declaration,
        marker="required_entity_signature",
        rule_id_prefix="API001/required_entity_signature/invalid_declaration",
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
    params_kwargs = without_none(declaration.params, _METHOD_OPTIONS)
    compiler_evidence: List[Evidence] = []

    mode = str(params_kwargs.get("signature_mode", "compatible")).lower()
    enforce_method_kind = bool_param(params_kwargs, "enforce_method_kind", default=True)
    allow_missing = bool_param(params_kwargs, "allow_missing", default=False)
    declared_only = bool_param(params_kwargs, "declared_only", default=False)
    name_match = str(params_kwargs.get("name_match", "exact")).lower()
    aliases_raw = params_kwargs.get("aliases")
    pattern = params_kwargs.get("pattern")

    if source_entity.kind != "method":
        return reject_misplaced(
            source_entity,
            invalid_target_evidence(
                source_entity,
                declaration,
                decorator="required_method",
                expected_kind="method",
            ),
            marker="required_method",
            rule_id_prefix="API002/required_method/invalid_declaration",
            rule_id_suffix=rule_id_suffix,
            valid=["method"],
            compiler_evidence=compiler_evidence,
        )

    rejected = reject_invalid_param(
        source_entity,
        declaration,
        options_problem(
            params_kwargs,
            choices={"signature_mode": _SIGNATURE_MODES},
            bools=_METHOD_BOOLS,
        ),
        marker="required_method",
        rule_id_prefix="API002/required_method/invalid_declaration",
        rule_id_suffix=rule_id_suffix,
        evidence_type="compiler_invalid_declaration",
    )
    if rejected is not None:
        return rejected

    problem = _name_match_problem(name_match, aliases_raw, pattern)
    if problem is not None:
        param, reason = problem
        compiler_evidence.append(
            invalid_declaration_evidence(
                source_entity,
                declaration,
                decorator="required_method",
                reason=reason,
                params=params_kwargs,
            )
        )
        return drop_with_sentinel(
            source_entity,
            compiler_evidence,
            marker="required_method",
            rule_id_prefix="API002/required_method/invalid_declaration",
            rule_id_suffix=rule_id_suffix,
            param=param,
            value=params_kwargs.get(param),
            valid=_NAME_MATCHES if param == "name_match" else None,
            reason=reason,
        )
    aliases = None if aliases_raw is None else [str(alias) for alias in aliases_raw]

    rejected = reject_invalid_severity(
        source_entity,
        declaration,
        marker="required_method",
        rule_id_prefix="API002/required_method/invalid_declaration",
        rule_id_suffix=rule_id_suffix,
        evidence_type="compiler_invalid_declaration",
        compiler_evidence=compiler_evidence,
    )
    if rejected is not None:
        return rejected

    base_severity = marker_severity(params_kwargs)

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
