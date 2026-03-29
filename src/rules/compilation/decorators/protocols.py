from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from src.config import Config
from src.core.models import Evidence
from src.entities import DeclarationEntry, Entity
from src.protocols.introspection import is_protocol_entity
from src.protocols.reference_resolution import (
    resolve_reference,
)

from ..common import canonicalize_payload, evidence_id, with_rule_id_suffix


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


def _protocol_rule_options(
    params_kwargs: dict[str, Any],
) -> tuple[str, str, Literal["error", "warning", "info"]]:
    mode = str(params_kwargs.get("signature_mode", "compatible")).lower()
    if mode not in {"compatible", "exact"}:
        mode = "compatible"

    return_annotation = str(params_kwargs.get("return_annotation", "warning")).lower()
    if return_annotation not in {"off", "warning", "error"}:
        return_annotation = "warning"

    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

    return mode, return_annotation, base_severity


def _resolve_protocol_entity(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    source_entities: list[Entity],
) -> tuple[Entity | None, str | None, list[Evidence]]:
    params_kwargs = dict(declaration.params)
    protocol_expr = str(
        params_kwargs.get("protocol_expr") or params_kwargs.get("protocol", "")
    ).strip()
    if not protocol_expr:
        payload = {
            "declaration": "implements_protocol",
            "issue": "compiler_invalid_protocol_reference",
            "reason": "missing_protocol",
        }
        return (
            None,
            None,
            [
                _evidence(
                    source_entity,
                    declaration,
                    evidence_type="compiler_invalid_protocol_reference",
                    payload=payload,
                )
            ],
        )

    resolution = resolve_reference(
        protocol_expr,
        context_entity=source_entity,
        entities=source_entities,
    )
    if resolution.entity is None or resolution.normalized is None:
        payload = {
            "declaration": "implements_protocol",
            "issue": "compiler_invalid_protocol_reference",
            "reason": resolution.reason or "ambiguous_or_missing",
            "protocol": protocol_expr,
            "normalized": resolution.normalized,
        }
        return (
            None,
            None,
            [
                _evidence(
                    source_entity,
                    declaration,
                    evidence_type="compiler_invalid_protocol_reference",
                    payload=payload,
                )
            ],
        )

    if not is_protocol_entity(resolution.entity, source_entities):
        payload = {
            "declaration": "implements_protocol",
            "issue": "compiler_invalid_protocol_reference",
            "reason": "not_typing_protocol",
            "protocol": protocol_expr,
            "normalized": resolution.normalized,
        }
        return (
            None,
            None,
            [
                _evidence(
                    source_entity,
                    declaration,
                    evidence_type="compiler_invalid_protocol_reference",
                    payload=payload,
                )
            ],
        )

    return resolution.entity, resolution.normalized, []


def _target_kind_error(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    payload: dict[str, Any],
) -> tuple[list[Any], list[Evidence], list[Any]]:
    compiler_evidence = [
        _evidence(
            source_entity,
            declaration,
            evidence_type="compiler_invalid_target",
            payload=payload,
        )
    ]
    return [], compiler_evidence, []


def _protocol_rule_metadata(
    declaration: DeclarationEntry,
) -> tuple[str, str, str, dict[str, Any], str, tuple[str, str]]:
    if declaration.surface == "signature":
        return (
            "PRO002/implements_protocol_signature/v1",
            "implements_protocol_signature",
            "function_or_method",
            {
                "subject_kind": declaration.subject_kind,
                "subject_index": declaration.subject_index,
                "subject_name": declaration.subject_name,
                "surface": declaration.surface,
            },
            "Protocol role typing mismatch for {target.module_path}:{target.qualname}: "
            "{details.reason}",
            (
                "Annotate the matched target parameter or return with a class "
                "that satisfies the protocol.",
                "Keep target role annotations resolvable through local or imported class names.",
            ),
        )
    return (
        "PRO001/implements_protocol/v1",
        "implements_protocol",
        "class",
        {},
        "Protocol conformance mismatch for {target.module_path}:{target.qualname}: "
        "{details.reason}",
        (
            "Implement all required protocol members on the target class.",
            "Match required method signatures and required attribute names/annotations.",
        ),
    )


def _compile_protocol_rule(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    source_entities: list[Entity],
    rule_id_suffix: str,
) -> Tuple[List[Any], List[Any], List[Any]]:
    from src.core.models import Rule, RuleSelector

    (
        rule_id,
        rule_name,
        expected_kind,
        extra_params,
        message_template,
        fix_hints,
    ) = _protocol_rule_metadata(declaration)
    if expected_kind == "class" and source_entity.kind != "class":
        payload = {
            "declaration": "implements_protocol",
            "issue": "compiler_invalid_target",
            "expected_kind": expected_kind,
            "found_kind": source_entity.kind,
        }
        return _target_kind_error(
            source_entity,
            declaration,
            payload=payload,
        )
    if expected_kind == "function_or_method" and source_entity.kind not in {
        "function",
        "method",
    }:
        payload = {
            "declaration": "implements_protocol",
            "issue": "compiler_invalid_target",
            "expected_kind": expected_kind,
            "found_kind": source_entity.kind,
            "surface": declaration.surface,
        }
        return _target_kind_error(
            source_entity,
            declaration,
            payload=payload,
        )

    compiler_evidence: List[Evidence] = []
    protocol_entity, protocol_ref, evidence_items = _resolve_protocol_entity(
        source_entity, declaration, source_entities=source_entities
    )
    compiler_evidence.extend(evidence_items)
    if protocol_entity is None or protocol_ref is None:
        return [], compiler_evidence, []

    params_kwargs = dict(declaration.params)
    mode, return_annotation, base_severity = _protocol_rule_options(params_kwargs)

    params = {
        "protocol": protocol_ref,
        "protocol_entity_id": protocol_entity.canonical_id,
        "signature_mode": mode,
        "enforce_method_kind": bool(params_kwargs.get("enforce_method_kind", True)),
        "return_annotation": return_annotation,
        "fail_on_unmatched": True,
    }
    params.update(extra_params)

    rule = Rule(
        rule_id=with_rule_id_suffix(rule_id, rule_id_suffix),
        rule_type="protocol_conformance",
        name=rule_name,
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params=params,
        message_template=message_template,
        fix_hints=fix_hints,
        enabled=True,
    )
    return [rule], compiler_evidence, []


def compile_implements_protocol(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    source_entities: list[Entity],
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    return _compile_protocol_rule(
        source_entity,
        declaration,
        source_entities=source_entities,
        rule_id_suffix=rule_id_suffix,
    )


__all__ = ["compile_implements_protocol"]
