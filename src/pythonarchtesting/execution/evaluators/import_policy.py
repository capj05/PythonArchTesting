from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Literal

from pythonarchtesting.core.compilation.common import canonicalize_payload, evidence_id
from pythonarchtesting.core.models import (
    EvalContext,
    Evidence,
    Rule,
    RuleResult,
    RuleStatus,
)
from pythonarchtesting.entities import Entity
from pythonarchtesting.execution.import_edges import (
    NormalizedImportEdge,
    collect_canonical_module_entities,
    collect_normalized_import_edges_for_modules,
)
from pythonarchtesting.execution.import_graph import (
    build_module_dependency_graph,
    filter_module_dependency_graph,
)
from pythonarchtesting.execution.import_policy_paths import (
    MAX_REPORTED_REACHABLE_PATHS,
    ImportPathStep,
    ReachableImportViolation,
    collect_reachable_import_violations,
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


def _build_direct_result(
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


def _build_occurrence_from_path_step(
    step: ImportPathStep,
    forbidden_prefix: str,
) -> Dict[str, Any]:
    return {
        "filepath": step.filepath_rel,
        "lineno": step.lineno,
        "imported_module": step.to_module,
        "forbidden_prefix": forbidden_prefix,
    }


def _build_reachable_violation_payload(
    *,
    violation: ReachableImportViolation,
    base_details: Dict[str, Any],
) -> Dict[str, Any]:
    step_payloads = [
        {
            "from_module": step.from_module,
            "to_module": step.to_module,
            "filepath": step.filepath_rel,
            "lineno": step.lineno,
            "in_type_checking": step.in_type_checking,
            "is_top_level": step.is_top_level,
        }
        for step in violation.steps
    ]
    return {
        "mode": base_details["mode"],
        "scope": base_details["scope"],
        "scope_value": base_details["scope_value"],
        "start_module": violation.start_module,
        "intermediate_modules": [step.to_module for step in violation.steps[:-1]],
        "forbidden_target": violation.forbidden_target,
        "forbidden_prefix": violation.forbidden_prefix,
        "path_length": len(violation.steps),
        "steps": step_payloads,
    }


def _build_reachable_violation_evidence(
    *,
    violations: tuple[ReachableImportViolation, ...],
    target: Entity,
    base_details: Dict[str, Any],
) -> tuple[Evidence, ...]:
    evidence_items: list[Evidence] = []
    for violation in violations:
        payload = _build_reachable_violation_payload(
            violation=violation,
            base_details=base_details,
        )
        first_step = violation.steps[0] if violation.steps else None
        evidence_items.append(
            Evidence(
                evidence_id=evidence_id("import_path", payload),
                type="import_path",
                source="ast",
                role="target",
                entity_id=target.canonical_id,
                payload=canonicalize_payload(payload),
                location=(
                    {
                        "filepath": first_step.filepath_rel,
                        "lineno": first_step.lineno,
                        "module": first_step.from_module,
                    }
                    if first_step is not None
                    else None
                ),
            )
        )
    return tuple(evidence_items)


def _build_reachable_violation_details(
    *,
    base_details: Dict[str, Any],
    violations: tuple[ReachableImportViolation, ...],
    reported_violations: tuple[ReachableImportViolation, ...],
) -> Dict[str, Any]:
    found_forbidden = {violation.forbidden_prefix for violation in violations}
    occurrences: list[Dict[str, Any]] = []
    seen_occurrences: set[tuple[str, int, str, str]] = set()

    for violation in violations:
        terminal_step = violation.steps[-1]
        occurrence = _build_occurrence_from_path_step(
            terminal_step,
            violation.forbidden_prefix,
        )
        occurrence_key = (
            str(occurrence["filepath"]),
            int(occurrence["lineno"]),
            str(occurrence["imported_module"]),
            str(occurrence["forbidden_prefix"]),
        )
        if occurrence_key in seen_occurrences:
            continue
        seen_occurrences.add(occurrence_key)
        occurrences.append(occurrence)

    violation_paths = [
        {
            "start_module": violation.start_module,
            "intermediate_modules": [step.to_module for step in violation.steps[:-1]],
            "forbidden_target": violation.forbidden_target,
            "forbidden_prefix": violation.forbidden_prefix,
            "path_length": len(violation.steps),
        }
        for violation in reported_violations
    ]
    path_count_total = len(violations)
    path_count_reported = len(reported_violations)
    return {
        **base_details,
        "forbidden_modules": sorted(found_forbidden),
        "occurrences": _sort_occurrences(occurrences),
        "path_count": path_count_total,
        "path_count_total": path_count_total,
        "path_count_reported": path_count_reported,
        "paths_truncated": path_count_total > path_count_reported,
        "start_modules": sorted({violation.start_module for violation in violations}),
        "forbidden_targets": sorted(
            {violation.forbidden_target for violation in violations}
        ),
        "violation_paths": violation_paths,
    }


def _build_reachable_message(
    *,
    base_details: Dict[str, Any],
    forbidden_modules: list[str],
    path_count_total: int,
) -> str:
    path_label = "path" if path_count_total == 1 else "paths"
    return (
        f"DEP001 reachable forbidden import paths found in {base_details['scope']} "
        f"'{base_details['scope_value']}': {forbidden_modules} "
        f"({path_count_total} {path_label})"
    )


def _collect_ignored_filepaths(
    *,
    entities: Iterable[Entity],
    ignore_globs: list[str],
) -> set[str]:
    if not ignore_globs:
        return set()

    return {
        entity.filepath_rel
        for entity in entities
        if any(
            fnmatch.fnmatch(entity.filepath_rel, pattern) for pattern in ignore_globs
        )
    }


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

    return _build_direct_result(
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
    canonical_module_entities = collect_canonical_module_entities(
        entities=ctx.target_index.all_sorted,
    )
    internal_modules = {
        entity.module_path: entity.filepath_rel
        for entity in canonical_module_entities
        if entity.module_path
    }
    all_modules = frozenset(internal_modules)
    imported_edges = collect_normalized_import_edges_for_modules(
        entities=canonical_module_entities,
        scope_modules=all_modules,
    )
    base_graph = build_module_dependency_graph(
        internal_modules=internal_modules,
        edges=imported_edges,
    )
    filtered_graph = filter_module_dependency_graph(
        base_graph,
        ignore_type_checking=ignore_type_checking,
        include_local_edges=False,
        ignored_filepaths=_collect_ignored_filepaths(
            entities=canonical_module_entities,
            ignore_globs=ignore_globs,
        ),
    )

    root_modules = sorted(
        module
        for module in scope.scope_modules
        if filtered_graph.nodes.get(module) is not None
        and filtered_graph.nodes[module].is_internal
        and _matches_prefix(module, allow) is None
    )
    violations = collect_reachable_import_violations(
        graph=filtered_graph,
        root_modules=root_modules,
        forbidden_prefixes=forbidden,
        allowed_prefixes=allow,
    )
    reported_violations = violations[:MAX_REPORTED_REACHABLE_PATHS]
    details = _build_reachable_violation_details(
        base_details=base_details,
        violations=violations,
        reported_violations=reported_violations,
    )

    if not violations:
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
        message=_build_reachable_message(
            base_details=base_details,
            forbidden_modules=details["forbidden_modules"],
            path_count_total=details["path_count_total"],
        ),
        evidence=_build_reachable_violation_evidence(
            violations=reported_violations,
            target=target,
            base_details=base_details,
        ),
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
