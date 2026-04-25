from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence, Rule, RuleSelector
from pythonarchtesting.entities import DeclarationEntry, Entity
from pythonarchtesting.protocols.entity_lookup import ProtocolEntityLookup
from pythonarchtesting.protocols.reference_resolution import normalize_reference

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


def _resolve_source_base_entity(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    declaration_name: str,
    source_entities: list[Entity],
) -> tuple[Entity | None, str | None, list[Evidence]]:
    base_ref = str(declaration.params.get("base", "")).strip()
    if not base_ref:
        payload = {
            "declaration": declaration_name,
            "issue": "compiler_invalid_base_reference",
            "reason": "missing_base",
        }
        return (
            None,
            None,
            [
                _evidence(
                    source_entity,
                    declaration,
                    evidence_type="compiler_invalid_base_reference",
                    payload=payload,
                )
            ],
        )

    lookup = ProtocolEntityLookup.from_entities(source_entities)
    aliases = lookup.import_aliases(source_entity.module_path)
    normalized, reason = normalize_reference(
        base_ref,
        module_path=source_entity.module_path,
        aliases=aliases,
    )
    if normalized is not None:
        base_entity = lookup.unique_class_by_fqn(normalized)
        if base_entity is not None:
            return base_entity, normalized, []

    should_try_simple_name = "." not in base_ref and base_ref not in aliases
    if should_try_simple_name:
        simple_matches = lookup.class_matches_by_name(base_ref)
        if len(simple_matches) == 1:
            base_entity = simple_matches[0]
            return base_entity, f"{base_entity.module_path}.{base_entity.name}", []
        if len(simple_matches) > 1:
            payload = {
                "declaration": declaration_name,
                "issue": "compiler_invalid_base_reference",
                "reason": "ambiguous_simple_name",
                "base": base_ref,
            }
            return (
                None,
                None,
                [
                    _evidence(
                        source_entity,
                        declaration,
                        evidence_type="compiler_invalid_base_reference",
                        payload=payload,
                    )
                ],
            )

    payload = {
        "declaration": declaration_name,
        "issue": "compiler_invalid_base_reference",
        "reason": reason or "ambiguous_or_missing",
        "base": base_ref,
    }
    if normalized is not None:
        payload["normalized"] = normalized
    return (
        None,
        None,
        [
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_base_reference",
                payload=payload,
            )
        ],
    )


def _resolve_rule_severity(
    params_kwargs: dict[str, Any],
) -> Literal["error", "warning", "info"]:
    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        return cast(Literal["error", "warning", "info"], base_severity_raw)
    return "error"


def _compile_nominal_rule(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    declaration_name: str,
    rule_name: str,
    rule_id: str,
    relationship_mode: str,
    allow_self: bool,
    transitive: bool,
    negated: bool,
    source_entities: list[Entity],
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    params_kwargs = dict(declaration.params)
    base_severity = _resolve_rule_severity(params_kwargs)

    if source_entity.kind != "class":
        payload = {
            "declaration": declaration_name,
            "issue": "compiler_invalid_target",
            "expected_kind": "class",
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

    compiler_evidence: list[Evidence] = []
    base_entity, normalized_base, evidence_items = _resolve_source_base_entity(
        source_entity,
        declaration,
        declaration_name=declaration_name,
        source_entities=source_entities,
    )
    compiler_evidence.extend(evidence_items)
    if base_entity is None or normalized_base is None:
        return [], compiler_evidence, []

    rule = Rule(
        rule_id=with_rule_id_suffix(rule_id, rule_id_suffix),
        rule_type="nominal_type_relationship",
        name=rule_name,
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            "base": str(params_kwargs.get("base", "")).strip(),
            "expected_source_base_id": base_entity.canonical_id,
            "relationship_mode": relationship_mode,
            "allow_self": allow_self,
            "negated": negated,
            "fail_on_unmatched": True,
            "transitive": transitive,
        },
        message_template=(
            "Nominal type relationship mismatch for "
            "{target.module_path}:{target.qualname}: {details.reason}"
        ),
        fix_hints=(
            "Align the target class with the required nominal relationship "
            "to the matched base counterpart.",
            "If nominal typing is not the right constraint, use a structural rule instead.",
        ),
        enabled=True,
    )
    return [rule], compiler_evidence, []


def compile_subclass_of(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    source_entities: list[Entity],
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_nominal_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="subclass_of",
        rule_name="subclass_of",
        rule_id="NOM001/subclass_of/v1",
        relationship_mode="subclass",
        allow_self=False,
        transitive=True,
        negated=False,
        source_entities=source_entities,
        rule_id_suffix=rule_id_suffix,
    )


def compile_exact_type(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    source_entities: list[Entity],
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_nominal_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="exact_type",
        rule_name="exact_type",
        rule_id="NOM001/exact_type/v1",
        relationship_mode="exact_type",
        allow_self=True,
        transitive=False,
        negated=False,
        source_entities=source_entities,
        rule_id_suffix=rule_id_suffix,
    )


def compile_not_subclass_of(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    source_entities: list[Entity],
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_nominal_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="not_subclass_of",
        rule_name="not_subclass_of",
        rule_id="NOM001/not_subclass_of/v1",
        relationship_mode="subclass",
        allow_self=False,
        transitive=True,
        negated=True,
        source_entities=source_entities,
        rule_id_suffix=rule_id_suffix,
    )


def compile_inherits_directly_from(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    source_entities: list[Entity],
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_nominal_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="inherits_directly_from",
        rule_name="inherits_directly_from",
        rule_id="NOM001/inherits_directly_from/v1",
        relationship_mode="subclass",
        allow_self=False,
        transitive=False,
        negated=False,
        source_entities=source_entities,
        rule_id_suffix=rule_id_suffix,
    )


__all__ = [
    "compile_exact_type",
    "compile_inherits_directly_from",
    "compile_not_subclass_of",
    "compile_subclass_of",
]
