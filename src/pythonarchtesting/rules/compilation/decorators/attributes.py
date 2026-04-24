from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import canonicalize_payload, evidence_id, with_rule_id_suffix

_VALID_STORAGE_VALUES = {"any", "instance", "class"}
_VALID_DESCRIPTOR_KINDS = {"cached_property", "classproperty"}


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


def _invalid_declaration(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    issue: str,
    **payload_extra: Any,
) -> Evidence:
    payload = {
        "declaration": "required_attribute",
        "issue": issue,
        **payload_extra,
    }
    return _evidence(
        source_entity,
        declaration,
        evidence_type="compiler_invalid_attribute_declaration",
        payload=payload,
    )


def _normalize_descriptor_kinds(
    value: Any,
) -> tuple[tuple[str, ...], bool]:
    if value is None:
        return (), True
    if not isinstance(value, (tuple, list)):
        return (), False

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            return (), False
        kind = item.strip().lower()
        if not kind:
            return (), False
        if kind in seen:
            continue
        seen.add(kind)
        normalized.append(kind)
    return tuple(normalized), True


def _bool_param(
    params: dict[str, Any], name: str, *, default: bool
) -> tuple[bool, bool]:
    value = params.get(name, default)
    if isinstance(value, bool):
        return value, True
    return default, False


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
        invalid_name_payload: dict[str, Any] = {
            "declaration": "required_attribute",
            "issue": "invalid_name",
            "name": name,
        }
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_attribute_declaration",
                payload=invalid_name_payload,
            )
        )
        return [], compiler_evidence, []

    storage = str(params_kwargs.get("storage", "any")).lower()
    if storage not in _VALID_STORAGE_VALUES:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_storage",
                storage=storage,
            )
        )
        return [], compiler_evidence, []

    allow_property = bool(params_kwargs.get("allow_property", False))
    require_writable = bool(params_kwargs.get("require_writable", False))
    declared_only = bool(params_kwargs.get("declared_only", False))
    allow_missing, allow_missing_valid = _bool_param(
        params_kwargs,
        "allow_missing",
        default=False,
    )
    if not allow_missing_valid:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_allow_missing",
                allow_missing=params_kwargs.get("allow_missing"),
            )
        )
        return [], compiler_evidence, []

    descriptor_kinds, descriptor_kinds_valid = _normalize_descriptor_kinds(
        params_kwargs.get("descriptor_kinds")
    )
    if params_kwargs.get("descriptor_kinds") is not None and not descriptor_kinds_valid:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_descriptor_kinds",
                descriptor_kinds=params_kwargs.get("descriptor_kinds"),
            )
        )
        return [], compiler_evidence, []

    unsupported_descriptor_kinds = tuple(
        kind for kind in descriptor_kinds if kind not in _VALID_DESCRIPTOR_KINDS
    )
    if unsupported_descriptor_kinds:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="unsupported_descriptor_kind",
                descriptor_kinds=descriptor_kinds,
                unsupported_descriptor_kinds=unsupported_descriptor_kinds,
            )
        )
        return [], compiler_evidence, []

    include_dynamic_attributes, include_dynamic_attributes_valid = _bool_param(
        params_kwargs,
        "include_dynamic_attributes",
        default=False,
    )
    if not include_dynamic_attributes_valid:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_include_dynamic_attributes",
                include_dynamic_attributes=params_kwargs.get(
                    "include_dynamic_attributes"
                ),
            )
        )
        return [], compiler_evidence, []

    interpret_dataclass_fields, interpret_dataclass_fields_valid = _bool_param(
        params_kwargs,
        "interpret_dataclass_fields",
        default=False,
    )
    if not interpret_dataclass_fields_valid:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_interpret_dataclass_fields",
                interpret_dataclass_fields=params_kwargs.get(
                    "interpret_dataclass_fields"
                ),
            )
        )
        return [], compiler_evidence, []

    if allow_property and storage == "class":
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="property_incompatible_with_class_storage",
                allow_property=True,
                storage=storage,
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

    uses_v2_surface = (
        params_kwargs.get("descriptor_kinds") is not None
        or include_dynamic_attributes
        or interpret_dataclass_fields
    )
    rule_id = (
        "API003/required_attribute/v2"
        if uses_v2_surface
        else "API003/required_attribute/v1"
    )

    rule = Rule(
        rule_id=with_rule_id_suffix(rule_id, rule_id_suffix),
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
            "allow_missing": allow_missing,
            "descriptor_kinds": descriptor_kinds,
            "include_dynamic_attributes": include_dynamic_attributes,
            "interpret_dataclass_fields": interpret_dataclass_fields,
            "fail_on_unmatched": not allow_missing,
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
