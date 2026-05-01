from __future__ import annotations

import re
from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity, build_canonical_id

from ..common import (
    build_invalid_param_sentinel_rule,
    canonicalize_payload,
    evidence_id,
    with_rule_id_suffix,
)

_VALID_MEMBER_KINDS = {"any", "method", "attribute", "property"}
_VALID_STORAGE_VALUES = {"any", "instance", "class"}
_VALID_NAME_MATCH = {"exact", "alias", "regex"}
_VALID_SIGNATURE_MODES = {"any", "compatible", "exact"}
_SENTINEL_RULE_ID_PREFIX = "NEG001/does_not_have/invalid_declaration"
_V2_PARAM_KEYS = frozenset(
    {
        "aliases",
        "include_descriptors",
        "include_dynamic_attributes",
        "name_match",
        "pattern",
        "signature_mode",
    }
)


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
        "declaration": "does_not_have",
        "issue": issue,
        **payload_extra,
    }
    return _evidence(
        source_entity,
        declaration,
        evidence_type="compiler_invalid_member_absence_declaration",
        payload=payload,
    )


def _enclosing_class_qualname(entity: Entity) -> str | None:
    if entity.kind != "method" or "." not in entity.qualname:
        return None
    return entity.qualname.rsplit(".", 1)[0]


def _owning_class_id(method_entity: Entity) -> str | None:
    class_qualname = _enclosing_class_qualname(method_entity)
    if class_qualname is None:
        return None
    return build_canonical_id(
        method_entity.role,
        method_entity.root_label,
        method_entity.module_path,
        class_qualname,
        "class",
        "-",
    )


def _normalized_aliases(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    aliases = [str(alias).strip() for alias in value]
    if any(not alias for alias in aliases):
        return None
    return aliases


def _drop(
    source_entity: Entity,
    *,
    param: str,
    value: Any,
    valid: list[str] | None,
    reason: str,
    compiler_evidence: list[Evidence],
    rule_id_suffix: str,
) -> Tuple[List[Any], List[Evidence], List[Any]]:
    sentinel = build_invalid_param_sentinel_rule(
        source_entity,
        decorator_name="does_not_have",
        rule_id_prefix=_SENTINEL_RULE_ID_PREFIX,
        param=param,
        value=value,
        valid=valid,
        reason=reason,
        rule_id_suffix=rule_id_suffix,
    )
    return [sentinel], compiler_evidence, []


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

    if declaration.surface != "body":
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="compiler_invalid_surface",
                expected_surface="body",
                found_surface=declaration.surface,
            )
        )
        return _drop(
            source_entity,
            param="declaration_surface",
            value=declaration.surface,
            valid=["body"],
            reason="does_not_have must be declared on a class or method body",
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    if source_entity.kind not in {"class", "method"}:
        compiler_evidence.append(
            _evidence(
                source_entity,
                declaration,
                evidence_type="compiler_invalid_target",
                payload={
                    "declaration": "does_not_have",
                    "issue": "compiler_invalid_target",
                    "expected_kind": "class_or_method",
                    "found_kind": source_entity.kind,
                },
            )
        )
        return _drop(
            source_entity,
            param="target_kind",
            value=source_entity.kind,
            valid=["class", "method"],
            reason="does_not_have must target a class or method",
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    raw_name = params_kwargs.get("name")
    if raw_name is not None and (not isinstance(raw_name, str) or not raw_name.strip()):
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_name",
                name=raw_name,
            )
        )
        return _drop(
            source_entity,
            param="name",
            value=raw_name,
            valid=None,
            reason="name must be a non-empty string",
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )
    name = raw_name.strip() if isinstance(raw_name, str) else None

    member_kind = str(params_kwargs.get("member_kind", "any")).lower()
    if member_kind not in _VALID_MEMBER_KINDS:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_member_kind",
                member_kind=member_kind,
            )
        )
        return _drop(
            source_entity,
            param="member_kind",
            value=member_kind,
            valid=sorted(_VALID_MEMBER_KINDS),
            reason="member_kind must be one of: any, method, attribute, property",
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
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
        return _drop(
            source_entity,
            param="storage",
            value=storage,
            valid=sorted(_VALID_STORAGE_VALUES),
            reason="storage must be one of: any, instance, class",
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    if member_kind in {"method", "property"} and storage != "any":
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_storage_for_member_kind",
                member_kind=member_kind,
                storage=storage,
            )
        )
        return _drop(
            source_entity,
            param="storage",
            value=storage,
            valid=["any"],
            reason=(
                f"storage must be 'any' when member_kind is '{member_kind}'"
            ),
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    name_match = str(params_kwargs.get("name_match", "exact")).lower()
    if name_match not in _VALID_NAME_MATCH:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_name_match",
                name_match=name_match,
            )
        )
        return _drop(
            source_entity,
            param="name_match",
            value=name_match,
            valid=sorted(_VALID_NAME_MATCH),
            reason="name_match must be one of: exact, alias, regex",
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    aliases = _normalized_aliases(params_kwargs.get("aliases"))
    if params_kwargs.get("aliases") is not None and aliases is None:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_aliases",
                aliases=params_kwargs.get("aliases"),
            )
        )
        return _drop(
            source_entity,
            param="aliases",
            value=params_kwargs.get("aliases"),
            valid=None,
            reason="aliases must be a list of non-empty strings",
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    pattern = params_kwargs.get("pattern")
    if pattern is not None and not isinstance(pattern, str):
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_pattern",
                pattern=pattern,
            )
        )
        return _drop(
            source_entity,
            param="pattern",
            value=pattern,
            valid=None,
            reason="pattern must be a string",
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    if name_match == "exact":
        if aliases not in (None, []):
            compiler_evidence.append(
                _invalid_declaration(
                    source_entity,
                    declaration,
                    issue="aliases_not_allowed_for_exact_name_match",
                )
            )
            return _drop(
                source_entity,
                param="aliases",
                value=aliases,
                valid=None,
                reason="aliases are not allowed when name_match='exact'",
                compiler_evidence=compiler_evidence,
                rule_id_suffix=rule_id_suffix,
            )
        if pattern is not None:
            compiler_evidence.append(
                _invalid_declaration(
                    source_entity,
                    declaration,
                    issue="pattern_not_allowed_for_exact_name_match",
                )
            )
            return _drop(
                source_entity,
                param="pattern",
                value=pattern,
                valid=None,
                reason="pattern is not allowed when name_match='exact'",
                compiler_evidence=compiler_evidence,
                rule_id_suffix=rule_id_suffix,
            )
    elif name_match == "alias":
        if not aliases:
            compiler_evidence.append(
                _invalid_declaration(
                    source_entity,
                    declaration,
                    issue="missing_aliases",
                )
            )
            return _drop(
                source_entity,
                param="aliases",
                value=aliases,
                valid=None,
                reason="aliases are required when name_match='alias'",
                compiler_evidence=compiler_evidence,
                rule_id_suffix=rule_id_suffix,
            )
        if pattern is not None:
            compiler_evidence.append(
                _invalid_declaration(
                    source_entity,
                    declaration,
                    issue="pattern_not_allowed_for_alias_name_match",
                )
            )
            return _drop(
                source_entity,
                param="pattern",
                value=pattern,
                valid=None,
                reason="pattern is not allowed when name_match='alias'",
                compiler_evidence=compiler_evidence,
                rule_id_suffix=rule_id_suffix,
            )
    elif name_match == "regex":
        if aliases not in (None, []):
            compiler_evidence.append(
                _invalid_declaration(
                    source_entity,
                    declaration,
                    issue="aliases_not_allowed_for_regex_name_match",
                )
            )
            return _drop(
                source_entity,
                param="aliases",
                value=aliases,
                valid=None,
                reason="aliases are not allowed when name_match='regex'",
                compiler_evidence=compiler_evidence,
                rule_id_suffix=rule_id_suffix,
            )
        if not isinstance(pattern, str) or not pattern.strip():
            compiler_evidence.append(
                _invalid_declaration(
                    source_entity,
                    declaration,
                    issue="missing_pattern",
                )
            )
            return _drop(
                source_entity,
                param="pattern",
                value=pattern,
                valid=None,
                reason="pattern is required when name_match='regex'",
                compiler_evidence=compiler_evidence,
                rule_id_suffix=rule_id_suffix,
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            compiler_evidence.append(
                _invalid_declaration(
                    source_entity,
                    declaration,
                    issue="invalid_pattern",
                    pattern=pattern,
                    error=str(exc),
                )
            )
            return _drop(
                source_entity,
                param="pattern",
                value=pattern,
                valid=None,
                reason=f"pattern is not a valid regex: {exc}",
                compiler_evidence=compiler_evidence,
                rule_id_suffix=rule_id_suffix,
            )

    signature_mode = str(params_kwargs.get("signature_mode", "any")).lower()
    if signature_mode not in _VALID_SIGNATURE_MODES:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_signature_mode",
                signature_mode=signature_mode,
            )
        )
        return _drop(
            source_entity,
            param="signature_mode",
            value=signature_mode,
            valid=sorted(_VALID_SIGNATURE_MODES),
            reason="signature_mode must be one of: any, compatible, exact",
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    include_descriptors = bool(params_kwargs.get("include_descriptors", False))
    include_dynamic_attributes = bool(
        params_kwargs.get("include_dynamic_attributes", False)
    )

    if signature_mode != "any" and member_kind not in {"method", "any"}:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_signature_mode_for_member_kind",
                signature_mode=signature_mode,
                member_kind=member_kind,
            )
        )
        return _drop(
            source_entity,
            param="signature_mode",
            value=signature_mode,
            valid=["any"],
            reason=(
                f"signature_mode must be 'any' when member_kind is '{member_kind}'"
            ),
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    if include_descriptors and member_kind == "method":
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="include_descriptors_not_supported_for_method_kind",
                member_kind=member_kind,
            )
        )
        return _drop(
            source_entity,
            param="include_descriptors",
            value=True,
            valid=["False"],
            reason="include_descriptors is not supported when member_kind='method'",
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    if include_dynamic_attributes and member_kind == "method":
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="include_dynamic_attributes_not_supported_for_method_kind",
                member_kind=member_kind,
            )
        )
        return _drop(
            source_entity,
            param="include_dynamic_attributes",
            value=True,
            valid=["False"],
            reason=(
                "include_dynamic_attributes is not supported when member_kind='method'"
            ),
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    selector_source_entity_id = source_entity.canonical_id
    signature_anchor_entity_id: str | None = None
    scope = cast(Literal["class", "method"], source_entity.kind)

    if source_entity.kind == "method":
        if member_kind not in {"method", "any"}:
            compiler_evidence.append(
                _invalid_declaration(
                    source_entity,
                    declaration,
                    issue="invalid_member_kind_for_method_body",
                    member_kind=member_kind,
                )
            )
            return _drop(
                source_entity,
                param="member_kind",
                value=member_kind,
                valid=["method", "any"],
                reason=(
                    "member_kind must be 'method' or 'any' when declared on a method body"
                ),
                compiler_evidence=compiler_evidence,
                rule_id_suffix=rule_id_suffix,
            )
        selector_source_entity_id = _owning_class_id(source_entity) or ""
        if not selector_source_entity_id:
            compiler_evidence.append(
                _invalid_declaration(
                    source_entity,
                    declaration,
                    issue="missing_owning_class_for_method_body",
                )
            )
            return _drop(
                source_entity,
                param="target_kind",
                value="orphan_method",
                valid=None,
                reason="does_not_have on a method requires an owning class",
                compiler_evidence=compiler_evidence,
                rule_id_suffix=rule_id_suffix,
            )
        signature_anchor_entity_id = source_entity.canonical_id
        if name is None:
            name = source_entity.name
        scope = "class"
    elif signature_mode != "any":
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="signature_mode_requires_method_body",
                signature_mode=signature_mode,
            )
        )
        return _drop(
            source_entity,
            param="signature_mode",
            value=signature_mode,
            valid=["any"],
            reason=(
                "signature_mode != 'any' requires the declaration to be on a method body"
            ),
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    if name_match == "exact" and name is None:
        compiler_evidence.append(
            _invalid_declaration(
                source_entity,
                declaration,
                issue="invalid_name",
                name=raw_name,
            )
        )
        return _drop(
            source_entity,
            param="name",
            value=None,
            valid=None,
            reason="name is required when name_match='exact'",
            compiler_evidence=compiler_evidence,
            rule_id_suffix=rule_id_suffix,
        )

    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

    v2_requested = (
        bool(_V2_PARAM_KEYS & set(params_kwargs)) or source_entity.kind == "method"
    )
    rule_id = "NEG001/does_not_have/v2" if v2_requested else "NEG001/does_not_have/v1"

    rule_params: dict[str, Any] = {
        "name": name,
        "member_kind": member_kind,
        "storage": storage,
        "declared_only": bool(params_kwargs.get("declared_only", False)),
        "fail_on_unmatched": False,
    }
    if v2_requested:
        rule_params.update(
            {
                "name_match": name_match,
                "aliases": aliases,
                "pattern": pattern.strip() if isinstance(pattern, str) else None,
                "signature_mode": signature_mode,
                "include_descriptors": include_descriptors,
                "include_dynamic_attributes": include_dynamic_attributes,
            }
        )
        if signature_anchor_entity_id is not None:
            rule_params["signature_anchor_entity_id"] = signature_anchor_entity_id

    rule = Rule(
        rule_id=with_rule_id_suffix(rule_id, rule_id_suffix),
        rule_type="member_absence",
        name="does_not_have",
        severity=base_severity,
        scope=scope,
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=selector_source_entity_id,
            explicit_target=None,
        ),
        params=rule_params,
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
