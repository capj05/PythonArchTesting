from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import canonicalize_payload, evidence_id, with_rule_id_suffix

_VALID_MEMBER_KINDS = {"any", "method", "attribute", "property"}
_VALID_STORAGE_VALUES = {"any", "instance", "class"}


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


def compile_does_not_have(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    from pythonarchtesting.core.models import Rule, RuleSelector

    _ = cfg
    params_kwargs = dict(declaration.params)
    compiler_evidence: list[Evidence] = []

    if source_entity.kind != "class":
        payload = {
            "declaration": "does_not_have",
            "issue": "compiler_invalid_target",
            "expected_kind": "class",
            "found_kind": source_entity.kind,
        }
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_target",
                payload=payload,
            )
        )
        return [], compiler_evidence, []

    if declaration.surface != "body":
        payload = {
            "declaration": "does_not_have",
            "issue": "compiler_invalid_surface",
            "expected_surface": "body",
            "found_surface": declaration.surface,
        }
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_member_absence_declaration",
                payload=payload,
            )
        )
        return [], compiler_evidence, []

    name = params_kwargs.get("name")
    if not isinstance(name, str) or not name.strip():
        payload = {
            "declaration": "does_not_have",
            "issue": "invalid_name",
            "name": name,
        }
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_member_absence_declaration",
                payload=payload,
            )
        )
        return [], compiler_evidence, []

    member_kind = str(params_kwargs.get("member_kind", "any")).lower()
    if member_kind not in _VALID_MEMBER_KINDS:
        payload = {
            "declaration": "does_not_have",
            "issue": "invalid_member_kind",
            "member_kind": member_kind,
        }
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_member_absence_declaration",
                payload=payload,
            )
        )
        return [], compiler_evidence, []

    storage = str(params_kwargs.get("storage", "any")).lower()
    if storage not in _VALID_STORAGE_VALUES:
        payload = {
            "declaration": "does_not_have",
            "issue": "invalid_storage",
            "storage": storage,
        }
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_member_absence_declaration",
                payload=payload,
            )
        )
        return [], compiler_evidence, []

    if member_kind in {"method", "property"} and storage != "any":
        payload = {
            "declaration": "does_not_have",
            "issue": "invalid_storage_for_member_kind",
            "member_kind": member_kind,
            "storage": storage,
        }
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_member_absence_declaration",
                payload=payload,
            )
        )
        return [], compiler_evidence, []

    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

    rule = Rule(
        rule_id=with_rule_id_suffix("NEG001/does_not_have/v1", rule_id_suffix),
        rule_type="member_absence",
        name="does_not_have",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            "name": name.strip(),
            "member_kind": member_kind,
            "storage": storage,
            "declared_only": bool(params_kwargs.get("declared_only", False)),
            "fail_on_unmatched": False,
        },
        message_template=(
            "Forbidden member present on {target.module_path}:{target.qualname}: "
            "{details.reason}"
        ),
        fix_hints=(
            "Remove the forbidden member or rename it.",
            (
                "If the member must exist, move the rule to a narrower target "
                "or adjust the member kind."
            ),
        ),
        enabled=True,
    )
    return [rule], compiler_evidence, []


__all__ = ["compile_does_not_have"]
