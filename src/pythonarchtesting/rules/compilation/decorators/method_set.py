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

_SENTINEL_RULE_ID_PREFIX = "API005/require_method_set/invalid_declaration"

_VALID_NAME_MATCH = frozenset({"any", "regex", "names"})
_VALID_METHOD_KINDS = frozenset({"any", "instance", "classmethod", "staticmethod"})


def _invalid_declaration_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    reason: str,
    params: dict[str, Any],
) -> Evidence:
    payload = {
        "decorator": "require_method_set",
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
        "decorator": "require_method_set",
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
        decorator_name="require_method_set",
        rule_id_prefix=_SENTINEL_RULE_ID_PREFIX,
        param=param,
        value=value,
        valid=valid,
        reason=reason,
        rule_id_suffix=rule_id_suffix,
    )
    return [sentinel], [evidence], []


def _normalize_names(raw_names: Any) -> tuple[list[str] | None, bool]:
    if raw_names is None:
        return None, True
    if not isinstance(raw_names, list):
        return None, False
    names = [str(name).strip() for name in raw_names]
    if any(not name for name in names):
        return None, False
    return names, True


def _normalize_nonnegative_int(value: Any) -> tuple[int | None, bool]:
    if value is None or isinstance(value, bool) or not isinstance(value, int):
        return None, False
    return value, value >= 0


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
        evidence = _invalid_target_evidence(source_entity, declaration)
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

    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

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


__all__ = ["compile_require_method_set"]
