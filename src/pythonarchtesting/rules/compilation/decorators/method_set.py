from __future__ import annotations

import re
from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import canonicalize_payload, evidence_id, with_rule_id_suffix

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
        compiler_evidence.append(_invalid_target_evidence(source_entity, declaration))
        return [], compiler_evidence, []

    if declaration.surface != "body":
        compiler_evidence.append(
            _invalid_declaration_evidence(
                source_entity,
                declaration,
                reason="require_method_set must be declared on a class body",
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
