from __future__ import annotations

import re
from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    build_invalid_param_sentinel_rule,
    canonicalize_payload,
    evidence_id,
    with_rule_id_suffix,
)
from .method_set import (
    _VALID_METHOD_KINDS,
    _VALID_NAME_MATCH,
    _normalize_names,
    _normalize_nonnegative_int,
)

_SENTINEL_RULE_ID_PREFIX = "API006/require_member_set/invalid_declaration"

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


def _drop(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    param: str,
    value: Any,
    valid: list[str] | None,
    reason: str,
    params_kwargs: dict[str, Any],
    rule_id_suffix: str,
) -> Tuple[List[Any], List[Evidence], List[Any]]:
    """Build a (sentinel-rule, compiler-evidence) pair for a dropped declaration."""
    evidence = _invalid_declaration_evidence(
        source_entity,
        declaration,
        reason=reason,
        params=params_kwargs,
    )
    sentinel = build_invalid_param_sentinel_rule(
        source_entity,
        decorator_name="require_member_set",
        rule_id_prefix=_SENTINEL_RULE_ID_PREFIX,
        param=param,
        value=value,
        valid=valid,
        reason=reason,
        rule_id_suffix=rule_id_suffix,
    )
    return [sentinel], [evidence], []


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
        evidence = _invalid_target_evidence(source_entity, declaration)
        sentinel = build_invalid_param_sentinel_rule(
            source_entity,
            decorator_name="require_member_set",
            rule_id_prefix=_SENTINEL_RULE_ID_PREFIX,
            param="target_kind",
            value=source_entity.kind,
            valid=["class"],
            reason="require_member_set must target a class",
            rule_id_suffix=rule_id_suffix,
        )
        return [sentinel], [evidence], []

    if declaration.surface != "body":
        return _drop(
            source_entity,
            declaration,
            param="declaration_surface",
            value=declaration.surface,
            valid=["body"],
            reason="require_member_set must be declared on a class body",
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

    member_kinds, member_kinds_valid = _normalize_member_kinds(
        params_kwargs.get("member_kinds")
    )
    if not member_kinds_valid or member_kinds is None:
        return _drop(
            source_entity,
            declaration,
            param="member_kinds",
            value=params_kwargs.get("member_kinds"),
            valid=sorted(_VALID_MEMBER_KINDS),
            reason=(
                "member_kinds must be a non-empty tuple/list of: "
                "any, method, attribute, property, descriptor, constructor; "
                "'any' cannot be combined with other kinds"
            ),
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

    name_match = str(params_kwargs.get("name_match", "any")).lower()
    if name_match not in _VALID_NAME_MATCH:
        return _drop(
            source_entity,
            declaration,
            param="name_match",
            value=params_kwargs.get("name_match"),
            valid=sorted(_VALID_NAME_MATCH),
            reason="name_match must be one of: any, regex, names",
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

    names, names_valid = _normalize_names(params_kwargs.get("names"))
    if not names_valid:
        return _drop(
            source_entity,
            declaration,
            param="names",
            value=params_kwargs.get("names"),
            valid=None,
            reason="names must be a list of non-empty strings",
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

    pattern = params_kwargs.get("pattern")
    if pattern is not None:
        if not isinstance(pattern, str) or not pattern.strip():
            return _drop(
                source_entity,
                declaration,
                param="pattern",
                value=pattern,
                valid=None,
                reason="pattern must be a non-empty string",
                params_kwargs=params_kwargs,
                rule_id_suffix=rule_id_suffix,
            )
        pattern = pattern.strip()

    if name_match == "names":
        if not names:
            return _drop(
                source_entity,
                declaration,
                param="names",
                value=names,
                valid=None,
                reason="name_match='names' requires a non-empty names list",
                params_kwargs=params_kwargs,
                rule_id_suffix=rule_id_suffix,
            )
        if pattern is not None:
            return _drop(
                source_entity,
                declaration,
                param="pattern",
                value=pattern,
                valid=None,
                reason="name_match='names' does not accept pattern",
                params_kwargs=params_kwargs,
                rule_id_suffix=rule_id_suffix,
            )
    elif name_match == "regex":
        if names not in (None, []):
            return _drop(
                source_entity,
                declaration,
                param="names",
                value=names,
                valid=None,
                reason="name_match='regex' does not accept names",
                params_kwargs=params_kwargs,
                rule_id_suffix=rule_id_suffix,
            )
        if pattern is None:
            return _drop(
                source_entity,
                declaration,
                param="pattern",
                value=None,
                valid=None,
                reason="name_match='regex' requires a non-empty pattern",
                params_kwargs=params_kwargs,
                rule_id_suffix=rule_id_suffix,
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            return _drop(
                source_entity,
                declaration,
                param="pattern",
                value=pattern,
                valid=None,
                reason=f"invalid regex pattern: {exc}",
                params_kwargs=params_kwargs,
                rule_id_suffix=rule_id_suffix,
            )
    elif names not in (None, []) or pattern is not None:
        return _drop(
            source_entity,
            declaration,
            param="names_or_pattern",
            value={"names": names, "pattern": pattern},
            valid=None,
            reason="name_match='any' does not accept names or pattern",
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

    method_kind = str(params_kwargs.get("method_kind", "any")).lower()
    if method_kind not in _VALID_METHOD_KINDS:
        return _drop(
            source_entity,
            declaration,
            param="method_kind",
            value=params_kwargs.get("method_kind"),
            valid=sorted(_VALID_METHOD_KINDS),
            reason=(
                "method_kind must be one of: any, instance, "
                "classmethod, staticmethod"
            ),
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

    storage = str(params_kwargs.get("storage", "any")).lower()
    if storage not in _VALID_STORAGE:
        return _drop(
            source_entity,
            declaration,
            param="storage",
            value=params_kwargs.get("storage"),
            valid=sorted(_VALID_STORAGE),
            reason="storage must be one of: any, instance, class",
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

    descriptor_kinds, descriptor_kinds_valid = _normalize_descriptor_kinds(
        params_kwargs.get("descriptor_kinds")
    )
    if not descriptor_kinds_valid:
        return _drop(
            source_entity,
            declaration,
            param="descriptor_kinds",
            value=params_kwargs.get("descriptor_kinds"),
            valid=sorted(_VALID_DESCRIPTOR_KINDS),
            reason=(
                "descriptor_kinds must be a non-empty tuple/list with values from: "
                "cached_property, classproperty"
            ),
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

    constructor_kind = str(params_kwargs.get("constructor_kind", "auto"))
    if constructor_kind not in _VALID_CONSTRUCTOR_KIND:
        return _drop(
            source_entity,
            declaration,
            param="constructor_kind",
            value=params_kwargs.get("constructor_kind"),
            valid=sorted(_VALID_CONSTRUCTOR_KIND),
            reason=(
                "constructor_kind must be one of: auto, __init__, __new__"
            ),
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

    min_count, min_count_valid = _normalize_nonnegative_int(
        params_kwargs.get("min_count", 1)
    )
    if not min_count_valid or min_count is None:
        return _drop(
            source_entity,
            declaration,
            param="min_count",
            value=params_kwargs.get("min_count"),
            valid=None,
            reason="min_count must be an integer >= 0",
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

    max_count_raw = params_kwargs.get("max_count")
    max_count: int | None
    if max_count_raw is None:
        max_count = None
    else:
        max_count, max_count_valid = _normalize_nonnegative_int(max_count_raw)
        if not max_count_valid or max_count is None:
            return _drop(
                source_entity,
                declaration,
                param="max_count",
                value=max_count_raw,
                valid=None,
                reason="max_count must be None or an integer >= 0",
                params_kwargs=params_kwargs,
                rule_id_suffix=rule_id_suffix,
            )

    if max_count is not None and max_count < min_count:
        return _drop(
            source_entity,
            declaration,
            param="max_count",
            value=max_count,
            valid=None,
            reason="max_count must be >= min_count",
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

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
