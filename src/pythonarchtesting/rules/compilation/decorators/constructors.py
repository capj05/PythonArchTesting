from __future__ import annotations

from typing import Any, List, Sequence, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity
from pythonarchtesting.execution.evaluators.construction_resolution import (
    resolve_source_constructor,
)

from ..common import (
    bool_param,
    invalid_declaration_evidence,
    invalid_target_evidence,
    marker_severity,
    with_rule_id_suffix,
)

_DECORATOR = "required_constructor"
_VALID_CONSTRUCTOR_KINDS = ("auto", "__init__", "__new__")
_VALID_SIGNATURE_MODES = ("compatible", "exact", "any")


def compile_required_constructor(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
    source_entities: Sequence[Entity] = (),
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compile required_constructor declarations into API003 signature rules."""
    from pythonarchtesting.core.models import Rule, RuleSelector

    _ = cfg
    params_kwargs = dict(declaration.params)
    compiler_evidence: List[Evidence] = []

    if source_entity.kind != "class":
        compiler_evidence.append(
            invalid_target_evidence(source_entity, declaration, decorator=_DECORATOR)
        )
        return [], compiler_evidence, []

    signature_mode = str(params_kwargs.get("signature_mode", "compatible")).lower()
    if signature_mode not in _VALID_SIGNATURE_MODES:
        compiler_evidence.append(
            invalid_declaration_evidence(
                source_entity,
                declaration,
                decorator=_DECORATOR,
                reason="signature_mode must be one of: compatible, exact, any",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    constructor_kind = str(params_kwargs.get("constructor_kind", "auto")).lower()
    if constructor_kind not in _VALID_CONSTRUCTOR_KINDS:
        compiler_evidence.append(
            invalid_declaration_evidence(
                source_entity,
                declaration,
                decorator=_DECORATOR,
                reason=("constructor_kind must be one of: auto, __init__, __new__"),
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    allow_inherited = bool(params_kwargs.get("allow_inherited", True))
    allow_missing, allow_missing_valid = bool_param(
        params_kwargs,
        "allow_missing",
        default=False,
    )
    if not allow_missing_valid:
        compiler_evidence.append(
            invalid_declaration_evidence(
                source_entity,
                declaration,
                decorator=_DECORATOR,
                reason="allow_missing must be a boolean",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    base_severity = marker_severity(params_kwargs)

    source_ctor = resolve_source_constructor(
        source_entity,
        source_entities,
        constructor_kind=constructor_kind,
    )

    if source_ctor is None:
        compiler_evidence.append(
            invalid_declaration_evidence(
                source_entity,
                declaration,
                decorator=_DECORATOR,
                reason=(
                    "source class has no declared constructor or dataclass-generated "
                    "__init__ matching "
                    f"constructor_kind={constructor_kind}"
                ),
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    selector = RuleSelector(
        source_entity_id=source_entity.canonical_id,
        explicit_target=None,
    )

    rule_id_version = (
        "API003/required_constructor/v2"
        if source_ctor.origin == "generated_dataclass_init"
        else "API003/required_constructor/v1"
    )

    rule_params = {
        "mode": signature_mode,
        "allow_extra_params": True,
        "allow_param_rename": False,
        "check_return": False,
        "fail_on_unmatched": not allow_missing,
        "enforce_method_kind": False,
        "constructor_kind": constructor_kind,
        "resolved_constructor_kind": source_ctor.kind,
        "allow_inherited": allow_inherited,
        "allow_missing": allow_missing,
        "source_constructor_origin": source_ctor.origin,
    }
    if source_ctor.origin == "generated_dataclass_init":
        rule_params["expected_source_constructor_context_id"] = (
            source_entity.canonical_id
        )
        rule_params["expected_source_constructor_model"] = (
            source_ctor.entity.extras.get("synthetic_param_model")
        )
    else:
        rule_params["expected_source_constructor_id"] = source_ctor.entity.canonical_id

    rule = Rule(
        rule_id=with_rule_id_suffix(rule_id_version, rule_id_suffix),
        rule_type="api_signature",
        name="required_constructor",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=selector,
        params=rule_params,
        message_template=(
            "Required constructor mismatch for "
            "{target.module_path}:{target.qualname}: {details.reason}"
        ),
        fix_hints=(
            "Implement a compatible constructor on the target class.",
            "Match the required parameter names, kinds, and required/optional shape.",
        ),
        enabled=True,
        version="v2" if source_ctor.origin == "generated_dataclass_init" else "v1",
    )

    return [rule], compiler_evidence, []


__all__ = ["compile_required_constructor"]
