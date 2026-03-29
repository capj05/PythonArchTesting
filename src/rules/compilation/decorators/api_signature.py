from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from src.config import Config
from src.entities import DeclarationEntry, Entity

from ..common import canonicalize_payload, evidence_id, with_rule_id_suffix


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
    from src.core.models import Rule, RuleSelector

    _ = cfg
    params_kwargs = dict(declaration.params)

    mode = str(params_kwargs.get("mode", "compatible")).lower()
    if mode not in {"compatible", "exact"}:
        mode = "compatible"

    allow_extra_params = bool(params_kwargs.get("allow_extra_params", True))
    allow_param_rename = bool(params_kwargs.get("allow_param_rename", False))

    return_annotation = str(params_kwargs.get("return_annotation", "warning")).lower()
    if return_annotation not in {"off", "warning", "error"}:
        return_annotation = "warning"

    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

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

    return rules, [], []


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
    from src.core.models import Evidence, Rule, RuleSelector

    _ = cfg
    params_kwargs = dict(declaration.params)
    compiler_evidence: List[Evidence] = []

    mode = str(params_kwargs.get("signature_mode", "compatible")).lower()
    if mode not in {"compatible", "exact"}:
        mode = "compatible"

    enforce_method_kind = bool(params_kwargs.get("enforce_method_kind", True))

    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

    location = {
        "filepath": source_entity.filepath_rel,
        "lineno": declaration.lineno or source_entity.lineno,
        "col": declaration.col,
    }

    if source_entity.kind != "method":
        payload = {
            "decorator": "required_method",
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
            "fail_on_unmatched": True,
            "enforce_method_kind": enforce_method_kind,
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
