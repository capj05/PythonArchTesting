from __future__ import annotations

from typing import Any, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    build_invalid_param_sentinel_rule,
    invalid_declaration_evidence,
    invalid_target_evidence,
    marker_severity,
    reject_invalid_severity,
    with_rule_id_suffix,
)
from .method_set import InvalidParam, parse_count_range, parse_name_selector

_DECORATOR = "require_member_set"
_SENTINEL_RULE_ID_PREFIX = "API006/require_member_set/invalid_declaration"

_VALID_MEMBER_KINDS = frozenset(
    {"any", "method", "attribute", "property", "descriptor", "constructor"}
)
_VALID_STORAGE = frozenset({"any", "instance", "class"})
_VALID_DESCRIPTOR_KINDS = frozenset({"cached_property", "classproperty"})
_VALID_CONSTRUCTOR_KIND = frozenset({"auto", "__init__", "__new__"})


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
    evidence = invalid_declaration_evidence(
        source_entity,
        declaration,
        decorator=_DECORATOR,
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
        evidence = invalid_target_evidence(
            source_entity, declaration, decorator=_DECORATOR
        )
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

    selector = parse_name_selector(params_kwargs)
    if isinstance(selector, InvalidParam):
        return _drop(
            source_entity,
            declaration,
            **selector.fields(),
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )
    name_match = selector.name_match
    names = selector.names
    pattern = selector.pattern
    method_kind = selector.method_kind

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
            reason=("constructor_kind must be one of: auto, __init__, __new__"),
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )

    counts = parse_count_range(params_kwargs)
    if isinstance(counts, InvalidParam):
        return _drop(
            source_entity,
            declaration,
            **counts.fields(),
            params_kwargs=params_kwargs,
            rule_id_suffix=rule_id_suffix,
        )
    min_count, max_count = counts

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

    rejected = reject_invalid_severity(
        source_entity,
        declaration,
        marker=_DECORATOR,
        rule_id_prefix=_SENTINEL_RULE_ID_PREFIX,
        rule_id_suffix=rule_id_suffix,
        evidence_type="compiler_invalid_declaration",
        compiler_evidence=compiler_evidence,
    )
    if rejected is not None:
        return rejected

    base_severity = marker_severity(params_kwargs)

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
