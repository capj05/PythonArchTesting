from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

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


def compile_required_attribute(
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
            "declaration": "required_attribute",
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
            "declaration": "required_attribute",
            "issue": "compiler_invalid_surface",
            "expected_surface": "body",
            "found_surface": declaration.surface,
        }
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_attribute_declaration",
                payload=payload,
            )
        )
        return [], compiler_evidence, []

    name = params_kwargs.get("name")
    if not isinstance(name, str) or not name.strip():
        payload = {
            "declaration": "required_attribute",
            "issue": "invalid_name",
            "name": name,
        }
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_attribute_declaration",
                payload=payload,
            )
        )
        return [], compiler_evidence, []

    storage = str(params_kwargs.get("storage", "any")).lower()
    if storage not in {"any", "instance", "class"}:
        payload = {
            "declaration": "required_attribute",
            "issue": "invalid_storage",
            "storage": storage,
        }
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_attribute_declaration",
                payload=payload,
            )
        )
        return [], compiler_evidence, []

    allow_property = bool(params_kwargs.get("allow_property", False))
    require_writable = bool(params_kwargs.get("require_writable", False))
    declared_only = bool(params_kwargs.get("declared_only", False))

    if allow_property and storage == "class":
        payload = {
            "declaration": "required_attribute",
            "issue": "property_incompatible_with_class_storage",
            "allow_property": True,
            "storage": storage,
        }
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_attribute_declaration",
                payload=payload,
            )
        )
        return [], compiler_evidence, []

    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

    annotation = params_kwargs.get("annotation")
    if annotation is not None:
        annotation = str(annotation).strip() or None

    rule = Rule(
        rule_id=with_rule_id_suffix("API003/required_attribute/v1", rule_id_suffix),
        rule_type="attribute_contract",
        name="required_attribute",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            "name": name.strip(),
            "annotation": annotation,
            "storage": storage,
            "allow_property": allow_property,
            "require_writable": require_writable,
            "declared_only": declared_only,
            "fail_on_unmatched": True,
        },
        message_template=(
            "Required attribute mismatch for {target.module_path}:{target.qualname}: "
            "{details.reason}"
        ),
        fix_hints=(
            "Declare the required attribute on the target class or instance.",
            "Match the expected annotation and requested storage kind.",
        ),
        enabled=True,
    )
    return [rule], compiler_evidence, []


__all__ = ["compile_required_attribute"]
