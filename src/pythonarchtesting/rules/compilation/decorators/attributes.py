from __future__ import annotations

from typing import Any, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    bool_param,
    declaration_evidence,
    drop_with_sentinel,
    invalid_target_evidence,
    marker_severity,
    options_problem,
    reject_invalid_param,
    reject_invalid_severity,
    reject_misplaced,
    with_rule_id_suffix,
    without_none,
)

_VALID_STORAGE_VALUES = {"any", "instance", "class"}
_VALID_DESCRIPTOR_KINDS = {"cached_property", "classproperty"}
_BOOLS = (
    "allow_property",
    "require_writable",
    "declared_only",
    "allow_missing",
    "include_dynamic_attributes",
    "interpret_dataclass_fields",
)
_OPTIONS = ("storage", *_BOOLS)


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
    return declaration_evidence(
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


def compile_required_attribute(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    from pythonarchtesting.core.models import Rule, RuleSelector

    _ = cfg
    params_kwargs = without_none(declaration.params, _OPTIONS)
    compiler_evidence: list[Evidence] = []
    drop: dict[str, Any] = {
        "marker": "required_attribute",
        "rule_id_prefix": "API003/required_attribute/invalid_declaration",
        "rule_id_suffix": rule_id_suffix,
    }
    reject: dict[str, Any] = {
        **drop,
        "evidence_type": "compiler_invalid_attribute_declaration",
        "key": "declaration",
    }

    if source_entity.kind != "class":
        return reject_misplaced(
            source_entity,
            invalid_target_evidence(
                source_entity,
                declaration,
                decorator="required_attribute",
                key="declaration",
            ),
            marker="required_attribute",
            rule_id_prefix=drop["rule_id_prefix"],
            rule_id_suffix=rule_id_suffix,
            valid=["class"],
            compiler_evidence=compiler_evidence,
        )

    if declaration.surface != "body":
        payload = {
            "declaration": "required_attribute",
            "issue": "compiler_invalid_surface",
            "expected_surface": "body",
            "found_surface": declaration.surface,
        }
        return reject_misplaced(
            source_entity,
            declaration_evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_attribute_declaration",
                payload=payload,
            ),
            marker="required_attribute",
            rule_id_prefix=drop["rule_id_prefix"],
            rule_id_suffix=rule_id_suffix,
            param="declaration_surface",
            value=declaration.surface,
            valid=["body"],
            reason="required_attribute must be declared on a class body",
            compiler_evidence=compiler_evidence,
        )

    name = params_kwargs.get("name")
    if not isinstance(name, str) or not name.strip():
        invalid_name_payload: dict[str, Any] = {
            "declaration": "required_attribute",
            "issue": "invalid_name",
            "name": name,
        }
        compiler_evidence.append(
            declaration_evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_attribute_declaration",
                payload=invalid_name_payload,
            )
        )
        return drop_with_sentinel(
            source_entity,
            compiler_evidence,
            **drop,
            param="name",
            value=name,
            reason="name must be a non-empty string",
        )

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
        return drop_with_sentinel(
            source_entity,
            compiler_evidence,
            **drop,
            param="storage",
            value=storage,
            valid=_VALID_STORAGE_VALUES,
            reason="storage must be one of: any, class, instance",
        )

    rejected = reject_invalid_param(
        source_entity,
        declaration,
        options_problem(params_kwargs, bools=_BOOLS),
        **reject,
    )
    if rejected is not None:
        return rejected
    flags = {name: bool_param(params_kwargs, name, default=False) for name in _BOOLS}
    allow_property = flags["allow_property"]

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
        return drop_with_sentinel(
            source_entity,
            compiler_evidence,
            **drop,
            param="descriptor_kinds",
            value=params_kwargs.get("descriptor_kinds"),
            reason="descriptor_kinds must be a list of non-empty strings",
        )

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
        return drop_with_sentinel(
            source_entity,
            compiler_evidence,
            **drop,
            param="descriptor_kinds",
            value=list(descriptor_kinds),
            valid=_VALID_DESCRIPTOR_KINDS,
            reason="descriptor_kinds may contain only: cached_property, classproperty",
        )

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
        return drop_with_sentinel(
            source_entity,
            compiler_evidence,
            **drop,
            param="allow_property",
            value=True,
            reason="allow_property=True does not combine with storage='class'",
        )

    rejected = reject_invalid_severity(
        source_entity,
        declaration,
        **reject,
        compiler_evidence=compiler_evidence,
    )
    if rejected is not None:
        return rejected

    base_severity = marker_severity(params_kwargs)

    annotation = params_kwargs.get("annotation")
    if annotation is not None:
        annotation = str(annotation).strip() or None

    uses_v2_surface = (
        params_kwargs.get("descriptor_kinds") is not None
        or flags["include_dynamic_attributes"]
        or flags["interpret_dataclass_fields"]
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
            "require_writable": flags["require_writable"],
            "declared_only": flags["declared_only"],
            "allow_missing": flags["allow_missing"],
            "descriptor_kinds": descriptor_kinds,
            "include_dynamic_attributes": flags["include_dynamic_attributes"],
            "interpret_dataclass_fields": flags["interpret_dataclass_fields"],
            "fail_on_unmatched": not flags["allow_missing"],
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
