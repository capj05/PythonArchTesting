from __future__ import annotations

import re
from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import canonicalize_payload, evidence_id, with_rule_id_suffix
from .method_set import (
    _VALID_METHOD_KINDS,
    _VALID_NAME_MATCH,
    _normalize_names,
    _normalize_nonnegative_int,
)

_VALID_MEMBER_KINDS = frozenset(
    {"any", "method", "attribute", "property", "descriptor", "constructor"}
)
_VALID_STORAGE = frozenset({"any", "instance", "class"})
_VALID_DESCRIPTOR_KINDS = frozenset({"cached_property", "classproperty"})
_VALID_CONSTRUCTOR_KIND = frozenset({"auto", "__init__", "__new__"})


def _invalid_declaration_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    reason: str,
    params: dict[str, Any],
) -> Evidence:
    payload = {
        "decorator": "require_member_set",
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
        "decorator": "require_member_set",
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


def _normalize_member_kinds(raw: Any) -> tuple[tuple[str, ...] | None, bool]:
    if raw is None:
        return ("any",), True
    if isinstance(raw, str):
        return None, False
    if not isinstance(raw, (list, tuple)):
        return None, False
    items = [str(item).lower() for item in raw]
    if not items:
        return None, False
    if any(item not in _VALID_MEMBER_KINDS for item in items):
        return None, False
    if "any" in items and len(items) > 1:
        return None, False
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return tuple(seen), True


def _normalize_descriptor_kinds(raw: Any) -> tuple[tuple[str, ...] | None, bool]:
    if raw is None:
        return None, True
    if isinstance(raw, str):
        return None, False
    if not isinstance(raw, (list, tuple)):
        return None, False
    items = [str(item) for item in raw]
    if not items:
        return None, False
    if any(item not in _VALID_DESCRIPTOR_KINDS for item in items):
        return None, False
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return tuple(seen), True


def compile_require_member_set(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compile require_member_set declarations into API006 member-set rules."""
    from pythonarchtesting.core.models import Rule, RuleSelector

    _ = cfg
    params_kwargs = dict(declaration.params)
    compiler_evidence: List[Evidence] = []

    if source_entity.kind != "class":
        compiler_evidence.append(_invalid_target_evidence(source_entity, declaration))
        return [], compiler_evidence, []

    if declaration.surface != "body":
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason="require_member_set must be declared on a class body",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    member_kinds, member_kinds_valid = _normalize_member_kinds(
        params_kwargs.get("member_kinds")
    )
    if not member_kinds_valid or member_kinds is None:
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason=(
                    "member_kinds must be a non-empty tuple/list of: "
                    "any, method, attribute, property, descriptor, constructor; "
                    "'any' cannot be combined with other kinds"
                ),
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    name_match = str(params_kwargs.get("name_match", "any")).lower()
    if name_match not in _VALID_NAME_MATCH:
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason="name_match must be one of: any, regex, names",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    names, names_valid = _normalize_names(params_kwargs.get("names"))
    if not names_valid:
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason="names must be a list of non-empty strings",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    pattern = params_kwargs.get("pattern")
    if pattern is not None:
        if not isinstance(pattern, str) or not pattern.strip():
            compiler_evidence.append(
                _invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    reason="pattern must be a non-empty string",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
        pattern = pattern.strip()

    if name_match == "names":
        if not names:
            compiler_evidence.append(
                _invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    reason="name_match='names' requires a non-empty names list",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
        if pattern is not None:
            compiler_evidence.append(
                _invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    reason="name_match='names' does not accept pattern",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
    elif name_match == "regex":
        if names not in (None, []):
            compiler_evidence.append(
                _invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    reason="name_match='regex' does not accept names",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
        if pattern is None:
            compiler_evidence.append(
                _invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    reason="name_match='regex' requires a non-empty pattern",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
        try:
            re.compile(pattern)
        except re.error as exc:
            compiler_evidence.append(
                _invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    reason=f"invalid regex pattern: {exc}",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []
    elif names not in (None, []) or pattern is not None:
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason="name_match='any' does not accept names or pattern",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    method_kind = str(params_kwargs.get("method_kind", "any")).lower()
    if method_kind not in _VALID_METHOD_KINDS:
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason=(
                    "method_kind must be one of: any, instance, "
                    "classmethod, staticmethod"
                ),
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    storage = str(params_kwargs.get("storage", "any")).lower()
    if storage not in _VALID_STORAGE:
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason="storage must be one of: any, instance, class",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    descriptor_kinds, descriptor_kinds_valid = _normalize_descriptor_kinds(
        params_kwargs.get("descriptor_kinds")
    )
    if not descriptor_kinds_valid:
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason=(
                    "descriptor_kinds must be a non-empty tuple/list with values from: "
                    "cached_property, classproperty"
                ),
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    constructor_kind = str(params_kwargs.get("constructor_kind", "auto"))
    if constructor_kind not in _VALID_CONSTRUCTOR_KIND:
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

    min_count, min_count_valid = _normalize_nonnegative_int(
        params_kwargs.get("min_count", 1)
    )
    if not min_count_valid or min_count is None:
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason="min_count must be an integer >= 0",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    max_count_raw = params_kwargs.get("max_count")
    max_count: int | None
    if max_count_raw is None:
        max_count = None
    else:
        max_count, max_count_valid = _normalize_nonnegative_int(max_count_raw)
        if not max_count_valid or max_count is None:
            compiler_evidence.append(
                _invalid_declaration_evidence(
                    source_entity,
                    declaration,
                    reason="max_count must be None or an integer >= 0",
                    params=params_kwargs,
                )
            )
            return [], compiler_evidence, []

    if max_count is not None and max_count < min_count:
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason="max_count must be >= min_count",
                params=params_kwargs,
            )
        )
        return [], compiler_evidence, []

    declared_only = bool(params_kwargs.get("declared_only", False))
    allow_property = bool(params_kwargs.get("allow_property", True))
    include_dynamic_attributes = bool(
        params_kwargs.get("include_dynamic_attributes", False)
    )
    interpret_dataclass_fields = bool(
        params_kwargs.get("interpret_dataclass_fields", False)
    )
    include_dataclass_constructor = bool(
        params_kwargs.get("include_dataclass_constructor", True)
    )

    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

    rule = Rule(
        rule_id=with_rule_id_suffix("API006/require_member_set/v1", rule_id_suffix),
        rule_type="member_set",
        name="require_member_set",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            "member_kinds": list(member_kinds),
            "name_match": name_match,
            "names": names,
            "pattern": pattern,
            "declared_only": declared_only,
            "method_kind": method_kind,
            "storage": storage,
            "allow_property": allow_property,
            "descriptor_kinds": list(descriptor_kinds) if descriptor_kinds else None,
            "include_dynamic_attributes": include_dynamic_attributes,
            "interpret_dataclass_fields": interpret_dataclass_fields,
            "constructor_kind": constructor_kind,
            "include_dataclass_constructor": include_dataclass_constructor,
            "min_count": min_count,
            "max_count": max_count,
            "fail_on_unmatched": True,
        },
        message_template=(
            "Member-set mismatch for {target.module_path}:{target.qualname}: "
            "{details.reason}"
        ),
        fix_hints=(
            "Add target members that satisfy the declared selector.",
            (
                "Adjust the target class so the number of matching members "
                "falls within the allowed range."
            ),
            (
                "Narrow or broaden the selector if the current match set is "
                "not the intended one."
            ),
        ),
        enabled=True,
    )

    return [rule], compiler_evidence, []


__all__ = ["compile_require_member_set"]
