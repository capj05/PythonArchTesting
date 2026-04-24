from __future__ import annotations

from typing import Any, List, Literal, Sequence, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity
from pythonarchtesting.protocols.introspection import declared_class_methods

from ..common import canonicalize_payload, evidence_id, with_rule_id_suffix

_VALID_CONSTRUCTOR_KINDS = ("auto", "__init__", "__new__")


def _invalid_declaration_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    reason: str,
    params: dict[str, Any],
) -> Evidence:
    payload = {
        "decorator": "required_constructor",
        "issue": "compiler_invalid_declaration",
        "reason": reason,
        "params": params,
    }
    location = {
        "filepath": source_entity.filepath_rel,
        "lineno": declaration.lineno or source_entity.lineno,
        "col": declaration.col,
    }
    return Evidence(
        evidence_id=evidence_id("compiler_invalid_declaration", payload),
        type="compiler_invalid_declaration",
        source="compiler",
        role="source",
        entity_id=source_entity.canonical_id,
        payload=canonicalize_payload(payload),
        location=location,
    )


def _invalid_target_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
) -> Evidence:
    payload = {
        "decorator": "required_constructor",
        "issue": "compiler_invalid_target",
        "expected_kind": "class",
        "found_kind": source_entity.kind,
    }
    location = {
        "filepath": source_entity.filepath_rel,
        "lineno": declaration.lineno or source_entity.lineno,
        "col": declaration.col,
    }
    return Evidence(
        evidence_id=evidence_id("compiler_invalid_target", payload),
        type="compiler_invalid_target",
        source="compiler",
        role="source",
        entity_id=source_entity.canonical_id,
        payload=canonicalize_payload(payload),
        location=location,
    )


def _find_declared_method(
    source_entity: Entity,
    source_entities: Sequence[Entity],
    name: str,
) -> Entity | None:
    for method in declared_class_methods(source_entity, list(source_entities)):
        if method.name == name:
            return method
    return None


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
            _invalid_target_evidence(source_entity, declaration)
        )
        return [], compiler_evidence, []

    signature_mode = str(params_kwargs.get("signature_mode", "compatible")).lower()
    if signature_mode not in {"compatible", "exact"}:
        signature_mode = "compatible"

    constructor_kind = str(params_kwargs.get("constructor_kind", "auto")).lower()
    if constructor_kind not in _VALID_CONSTRUCTOR_KINDS:
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason=(
                    "constructor_kind must be one of: auto, __init__, __new__"
                ),
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    allow_inherited = bool(params_kwargs.get("allow_inherited", True))

    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

    source_ctor: Entity | None = None
    resolved_kind: str = constructor_kind
    if constructor_kind == "auto":
        source_ctor = _find_declared_method(
            source_entity, source_entities, "__init__"
        )
        if source_ctor is not None:
            resolved_kind = "__init__"
        else:
            source_ctor = _find_declared_method(
                source_entity, source_entities, "__new__"
            )
            if source_ctor is not None:
                resolved_kind = "__new__"
    else:
        source_ctor = _find_declared_method(
            source_entity, source_entities, constructor_kind
        )

    if source_ctor is None:
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason=(
                    "source class has no declared constructor matching "
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

    rule = Rule(
        rule_id=with_rule_id_suffix(
            "API003/required_constructor/v1", rule_id_suffix
        ),
        rule_type="api_signature",
        name="required_constructor",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=selector,
        params={
            "mode": signature_mode,
            "allow_extra_params": True,
            "allow_param_rename": False,
            "check_return": False,
            "fail_on_unmatched": True,
            "enforce_method_kind": False,
            "constructor_kind": constructor_kind,
            "resolved_constructor_kind": resolved_kind,
            "allow_inherited": allow_inherited,
            "expected_source_constructor_id": source_ctor.canonical_id,
        },
        message_template=(
            "Required constructor mismatch for "
            "{target.module_path}:{target.qualname}: {details.reason}"
        ),
        fix_hints=(
            "Implement a compatible constructor on the target class.",
            "Match the required parameter names, kinds, and required/optional shape.",
        ),
        enabled=True,
    )

    return [rule], compiler_evidence, []


__all__ = ["compile_required_constructor"]
