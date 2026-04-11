from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.execution.import_edges import (
    collect_normalized_import_edges_for_modules,
)
from pythonarchtesting.matching import MatchResult


def _matches_prefix(name: str, prefixes: List[str]) -> str | None:
    for prefix in prefixes:
        if name == prefix or name.startswith(prefix + "."):
            return prefix
    return None


def _normalize_scope_name(raw_scope: Any) -> Literal["module", "package"]:
    scope = str(raw_scope).lower()
    if scope == "entity":
        return "module"
    if scope == "module":
        return "module"
    return "package"


@dataclass(frozen=True)
class ImportPolicyScope:
    scope_kind: Literal["module", "package"]
    scope_value: str
    scope_modules: frozenset[str]


def _resolve_import_policy_scope(
    *,
    rule: Rule,
    source: Entity,
    target: Entity,
    ctx: EvalContext,
) -> ImportPolicyScope:
    scope_kind = _normalize_scope_name(rule.params.get("scope", "package"))
    if scope_kind == "module":
        return ImportPolicyScope(
            scope_kind="module",
            scope_value=target.module_path,
            scope_modules=frozenset({target.module_path}),
        )

    configured_package = rule.params.get("package")
    if isinstance(configured_package, str) and configured_package:
        scope_value = configured_package
    else:
        scope_value = source.module_path.split(".")[0] if source.module_path else ""

    scope_modules = frozenset(
        entity.module_path
        for entity in ctx.target_index.all_sorted
        if entity.module_path == scope_value
        or entity.module_path.startswith(scope_value + ".")
    )
    return ImportPolicyScope(
        scope_kind="package",
        scope_value=scope_value,
        scope_modules=scope_modules,
    )


def _error_result(
    *,
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    message: str,
    details: Dict[str, Any],
) -> RuleResult:
    return RuleResult(
        rule_id=rule.rule_id,
        status="ERROR",
        source_entity_id=source.canonical_id,
        target_entity_id=target.canonical_id,
        match_status=match.status.value,
        confidence=match.confidence,
        message=message,
        evidence=(),
        details=details,
    )


class ImportPolicyEvaluator:
    """Evaluator for forbidden import policy rules (DEP001)."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        forbidden = [str(item) for item in list(rule.params.get("forbidden", []))]
        allow = [str(item) for item in list(rule.params.get("allow", []))]
        ignore_globs = [str(item) for item in list(rule.params.get("ignore_globs", []))]
        ignore_type_checking = bool(rule.params.get("ignore_type_checking", True))
        mode = str(rule.params.get("mode", "reachable"))
        scope = _resolve_import_policy_scope(
            rule=rule,
            source=source,
            target=target,
            ctx=ctx,
        )

        base_details = {
            "scope": scope.scope_kind,
            "scope_value": scope.scope_value,
            "match_status": match.status.value,
            "mode": mode,
        }

        if mode == "reachable":
            return _error_result(
                rule=rule,
                source=source,
                target=target,
                match=match,
                message=(
                    "DEP001 reachable import policy mode is the default semantic "
                    "contract, but reachability analysis is not implemented yet."
                ),
                details={
                    **base_details,
                    "reason": "reachable_mode_not_implemented",
                    "forbidden_modules": sorted(set(forbidden)),
                    "occurrences": [],
                },
            )

        if mode != "direct":
            return _error_result(
                rule=rule,
                source=source,
                target=target,
                match=match,
                message=f"DEP001 import policy received unsupported mode: {mode!r}.",
                details={
                    **base_details,
                    "reason": "invalid_mode",
                    "forbidden_modules": sorted(set(forbidden)),
                    "occurrences": [],
                },
            )

        imported_edges = collect_normalized_import_edges_for_modules(
            entities=ctx.target_index.all_sorted,
            scope_modules=scope.scope_modules,
            ignore_globs=ignore_globs,
        )

        occurrences: List[Dict[str, Any]] = []
        found_forbidden: set[str] = set()

        for edge in imported_edges:
            if ignore_type_checking and edge.in_type_checking:
                continue
            if _matches_prefix(edge.imported_module, allow) is not None:
                continue
            matched = _matches_prefix(edge.imported_module, forbidden)
            if matched is None:
                continue
            found_forbidden.add(matched)
            occurrences.append(
                {
                    "filepath": edge.filepath_rel,
                    "lineno": edge.lineno,
                    "imported_module": edge.imported_module,
                    "forbidden_prefix": matched,
                }
            )

        occurrences = sorted(
            occurrences,
            key=lambda item: (
                str(item.get("filepath", "")),
                int(item.get("lineno", 0)),
                str(item.get("imported_module", "")),
            ),
        )
        forbidden_modules = sorted(found_forbidden)
        status: RuleStatus = "FAILED" if occurrences else "OK"
        details = {
            **base_details,
            "forbidden_modules": forbidden_modules,
            "occurrences": occurrences,
        }

        if status == "OK":
            return RuleResult(
                rule_id=rule.rule_id,
                status="OK",
                source_entity_id=source.canonical_id,
                target_entity_id=target.canonical_id,
                match_status=match.status.value,
                confidence=match.confidence,
                message="OK",
                evidence=(),
                details=details,
            )

        message = (
            f"DEP001 forbidden imports found in {scope.scope_kind} "
            f"'{scope.scope_value}': "
            f"{forbidden_modules}"
        )
        return RuleResult(
            rule_id=rule.rule_id,
            status="FAILED",
            source_entity_id=source.canonical_id,
            target_entity_id=target.canonical_id,
            match_status=match.status.value,
            confidence=match.confidence,
            message=message,
            evidence=(),
            details=details,
        )


__all__ = ["ImportPolicyEvaluator"]
