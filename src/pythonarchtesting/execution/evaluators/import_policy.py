from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Literal

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.execution.import_edges import (
    NormalizedImportEdge,
    collect_canonical_module_entities,
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


def _build_occurrence(
    edge: NormalizedImportEdge,
    matched_prefix: str,
) -> Dict[str, Any]:
    return {
        "filepath": edge.filepath_rel,
        "lineno": edge.lineno,
        "imported_module": edge.imported_module,
        "forbidden_prefix": matched_prefix,
    }


def _sort_occurrences(
    occurrences: Iterable[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    return sorted(
        occurrences,
        key=lambda item: (
            str(item.get("filepath", "")),
            int(item.get("lineno", 0)),
            str(item.get("imported_module", "")),
        ),
    )


def _build_result(
    *,
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    base_details: Dict[str, Any],
    found_forbidden: set[str],
    occurrences: Iterable[Dict[str, Any]],
) -> RuleResult:
    ordered_occurrences = _sort_occurrences(occurrences)
    forbidden_modules = sorted(found_forbidden)
    status: RuleStatus = "FAILED" if ordered_occurrences else "OK"
    details = {
        **base_details,
        "forbidden_modules": forbidden_modules,
        "occurrences": ordered_occurrences,
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

    return RuleResult(
        rule_id=rule.rule_id,
        status="FAILED",
        source_entity_id=source.canonical_id,
        target_entity_id=target.canonical_id,
        match_status=match.status.value,
        confidence=match.confidence,
        message=(
            f"DEP001 forbidden imports found in {base_details['scope']} "
            f"'{base_details['scope_value']}': {forbidden_modules}"
        ),
        evidence=(),
        details=details,
    )


def _evaluate_direct_mode(
    *,
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    ctx: EvalContext,
    scope: ImportPolicyScope,
    base_details: Dict[str, Any],
    forbidden: list[str],
    allow: list[str],
    ignore_globs: list[str],
    ignore_type_checking: bool,
) -> RuleResult:
    imported_edges = collect_normalized_import_edges_for_modules(
        entities=ctx.target_index.all_sorted,
        scope_modules=scope.scope_modules,
        ignore_globs=ignore_globs,
    )

    occurrences: list[Dict[str, Any]] = []
    found_forbidden: set[str] = set()
    seen_occurrences: set[tuple[str, int, str, str]] = set()

    for edge in imported_edges:
        if ignore_type_checking and edge.in_type_checking:
            continue
        if _matches_prefix(edge.imported_module, allow) is not None:
            continue
        matched = _matches_prefix(edge.imported_module, forbidden)
        if matched is None:
            continue

        occurrence_key = (
            edge.filepath_rel,
            edge.lineno,
            edge.imported_module,
            matched,
        )
        if occurrence_key in seen_occurrences:
            continue
        seen_occurrences.add(occurrence_key)
        found_forbidden.add(matched)
        occurrences.append(_build_occurrence(edge, matched))

    return _build_result(
        rule=rule,
        source=source,
        target=target,
        match=match,
        base_details=base_details,
        found_forbidden=found_forbidden,
        occurrences=occurrences,
    )


def _evaluate_reachable_mode(
    *,
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    ctx: EvalContext,
    scope: ImportPolicyScope,
    base_details: Dict[str, Any],
    forbidden: list[str],
    allow: list[str],
    ignore_globs: list[str],
    ignore_type_checking: bool,
) -> RuleResult:
    active_module_entities = collect_canonical_module_entities(
        entities=ctx.target_index.all_sorted,
        ignore_globs=ignore_globs,
    )
    active_modules = frozenset(
        entity.module_path for entity in active_module_entities if entity.module_path
    )
    imported_edges = collect_normalized_import_edges_for_modules(
        entities=active_module_entities,
        scope_modules=active_modules,
    )

    adjacency: dict[str, list[NormalizedImportEdge]] = {}
    for edge in imported_edges:
        if ignore_type_checking and edge.in_type_checking:
            continue
        if not edge.is_top_level:
            continue
        adjacency.setdefault(edge.importer_module, []).append(edge)

    for edges in adjacency.values():
        edges.sort(
            key=lambda edge: (
                edge.filepath_rel,
                edge.lineno,
                edge.imported_module,
            )
        )

    root_modules = sorted(
        module
        for module in scope.scope_modules
        if module in active_modules and _matches_prefix(module, allow) is None
    )
    pending_modules = deque(root_modules)
    visited_modules: set[str] = set()
    found_forbidden: set[str] = set()
    occurrences: list[Dict[str, Any]] = []
    seen_occurrences: set[tuple[str, int, str, str]] = set()

    while pending_modules:
        module_name = pending_modules.popleft()
        if module_name in visited_modules:
            continue
        visited_modules.add(module_name)

        for edge in adjacency.get(module_name, []):
            if _matches_prefix(edge.imported_module, allow) is not None:
                continue

            matched = _matches_prefix(edge.imported_module, forbidden)
            if matched is not None:
                occurrence_key = (
                    edge.filepath_rel,
                    edge.lineno,
                    edge.imported_module,
                    matched,
                )
                if occurrence_key not in seen_occurrences:
                    seen_occurrences.add(occurrence_key)
                    found_forbidden.add(matched)
                    occurrences.append(_build_occurrence(edge, matched))
                continue

            if edge.imported_module in active_modules:
                pending_modules.append(edge.imported_module)

    return _build_result(
        rule=rule,
        source=source,
        target=target,
        match=match,
        base_details=base_details,
        found_forbidden=found_forbidden,
        occurrences=occurrences,
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
            return _evaluate_reachable_mode(
                rule=rule,
                source=source,
                target=target,
                match=match,
                ctx=ctx,
                scope=scope,
                base_details=base_details,
                forbidden=forbidden,
                allow=allow,
                ignore_globs=ignore_globs,
                ignore_type_checking=ignore_type_checking,
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

        return _evaluate_direct_mode(
            rule=rule,
            source=source,
            target=target,
            match=match,
            ctx=ctx,
            scope=scope,
            base_details=base_details,
            forbidden=forbidden,
            allow=allow,
            ignore_globs=ignore_globs,
            ignore_type_checking=ignore_type_checking,
        )


__all__ = ["ImportPolicyEvaluator"]
