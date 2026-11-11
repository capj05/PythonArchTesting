from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    InvalidParam,
    build_invalid_param_sentinel_rule,
    invalid_declaration_evidence,
    invalid_target_evidence,
    marker_severity,
    reject_invalid_severity,
    with_rule_id_suffix,
)

_DECORATOR = "require_method_set"
_SENTINEL_RULE_ID_PREFIX = "API005/require_method_set/invalid_declaration"

VALID_NAME_MATCH = frozenset({"any", "regex", "names"})
VALID_METHOD_KINDS = frozenset({"any", "instance", "classmethod", "staticmethod"})


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
        decorator_name="require_method_set",
        rule_id_prefix=_SENTINEL_RULE_ID_PREFIX,
        param=param,
        value=value,
        valid=valid,
        reason=reason,
        rule_id_suffix=rule_id_suffix,
    )
    return [sentinel], [evidence], []


def normalize_names(raw_names: Any) -> tuple[list[str] | None, bool]:
    if raw_names is None:
        return None, True
    if not isinstance(raw_names, list):
        return None, False
    names = [str(name).strip() for name in raw_names]
    if any(not name for name in names):
        return None, False
    return names, True


def normalize_nonnegative_int(value: Any) -> tuple[int | None, bool]:
    if value is None or isinstance(value, bool) or not isinstance(value, int):
        return None, False
    return value, value >= 0


@dataclass(frozen=True)
class NameSelector:
    """Which members of the class a set marker counts: by name (``any``,
    ``regex`` with a ``pattern``, or ``names``) and by method kind."""

    name_match: str
    names: list[str] | None
    pattern: str | None
    method_kind: str


def parse_name_selector(params_kwargs: dict[str, Any]) -> NameSelector | InvalidParam:
    """The name selector ``require_method_set`` and ``require_member_set``
    declare, or the first of its parameters the compiler refuses, checked in
    a fixed order: ``name_match``, ``names``, ``pattern``, their combination,
    ``method_kind``."""
    name_match = str(params_kwargs.get("name_match", "any")).lower()
    if name_match not in VALID_NAME_MATCH:
        return InvalidParam(
            param="name_match",
            value=params_kwargs.get("name_match"),
            valid=sorted(VALID_NAME_MATCH),
            reason="name_match must be one of: any, regex, names",
        )

    names, names_valid = normalize_names(params_kwargs.get("names"))
    if not names_valid:
        return InvalidParam(
            param="names",
            value=params_kwargs.get("names"),
            valid=None,
            reason="names must be a list of non-empty strings",
        )

    pattern = params_kwargs.get("pattern")
    if pattern is not None:
        if not isinstance(pattern, str) or not pattern.strip():
            return InvalidParam(
                param="pattern",
                value=pattern,
                valid=None,
                reason="pattern must be a non-empty string",
            )
        pattern = pattern.strip()

    if name_match == "names":
        if not names:
            return InvalidParam(
                param="names",
                value=names,
                valid=None,
                reason="name_match='names' requires a non-empty names list",
            )
        if pattern is not None:
            return InvalidParam(
                param="pattern",
                value=pattern,
                valid=None,
                reason="name_match='names' does not accept pattern",
            )
    elif name_match == "regex":
        if names not in (None, []):
            return InvalidParam(
                param="names",
                value=names,
                valid=None,
                reason="name_match='regex' does not accept names",
            )
        if pattern is None:
            return InvalidParam(
                param="pattern",
                value=None,
                valid=None,
                reason="name_match='regex' requires a non-empty pattern",
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            return InvalidParam(
                param="pattern",
                value=pattern,
                valid=None,
                reason=f"invalid regex pattern: {exc}",
            )
    elif names not in (None, []) or pattern is not None:
        return InvalidParam(
            param="names_or_pattern",
            value={"names": names, "pattern": pattern},
            valid=None,
            reason="name_match='any' does not accept names or pattern",
        )

    method_kind = str(params_kwargs.get("method_kind", "any")).lower()
    if method_kind not in VALID_METHOD_KINDS:
        return InvalidParam(
            param="method_kind",
            value=params_kwargs.get("method_kind"),
            valid=sorted(VALID_METHOD_KINDS),
            reason=(
                "method_kind must be one of: any, instance, "
                "classmethod, staticmethod"
            ),
        )

    return NameSelector(
        name_match=name_match, names=names, pattern=pattern, method_kind=method_kind
    )


def parse_count_range(
    params_kwargs: dict[str, Any],
) -> tuple[int, int | None] | InvalidParam:
    """The ``min_count`` (1 by default) and ``max_count`` (``None``: no upper
    bound) of a set marker, or the first of them the compiler refuses."""
    min_count, min_count_valid = normalize_nonnegative_int(
        params_kwargs.get("min_count", 1)
    )
    if not min_count_valid or min_count is None:
        return InvalidParam(
            param="min_count",
            value=params_kwargs.get("min_count"),
            valid=None,
            reason="min_count must be an integer >= 0",
        )

    max_count_raw = params_kwargs.get("max_count")
    max_count: int | None
    if max_count_raw is None:
        max_count = None
    else:
        max_count, max_count_valid = normalize_nonnegative_int(max_count_raw)
        if not max_count_valid or max_count is None:
            return InvalidParam(
                param="max_count",
                value=max_count_raw,
                valid=None,
                reason="max_count must be None or an integer >= 0",
            )

    if max_count is not None and max_count < min_count:
        return InvalidParam(
            param="max_count",
            value=max_count,
            valid=None,
            reason="max_count must be >= min_count",
        )

    return min_count, max_count


def compile_require_method_set(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compile require_method_set declarations into API005 method-set rules."""
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
            decorator_name="require_method_set",
            rule_id_prefix=_SENTINEL_RULE_ID_PREFIX,
            param="target_kind",
            value=source_entity.kind,
            valid=["class"],
            reason="require_method_set must target a class",
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
            reason="require_method_set must be declared on a class body",
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
        rule_id=with_rule_id_suffix("API005/require_method_set/v1", rule_id_suffix),
        rule_type="method_set",
        name="require_method_set",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            "name_match": name_match,
            "names": names,
            "pattern": pattern,
            "declared_only": declared_only,
            "method_kind": method_kind,
            "min_count": min_count,
            "max_count": max_count,
            "fail_on_unmatched": True,
        },
        message_template=(
            "Method-set mismatch for {target.module_path}:{target.qualname}: "
            "{details.reason}"
        ),
        fix_hints=(
            "Add target methods that satisfy the declared selector.",
            (
                "Adjust the target class so the number of matching methods "
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


__all__ = [
    "InvalidParam",
    "NameSelector",
    "compile_require_method_set",
    "VALID_METHOD_KINDS",
    "VALID_NAME_MATCH",
    "normalize_names",
    "normalize_nonnegative_int",
    "parse_count_range",
    "parse_name_selector",
]
