"""Evaluators for ``enforce_layers`` and ``forbid_cycles``.

The static rules judge the target's import graph as a whole, the runtime
rules the calls between modules while the entry function runs. At run time a
call against the layer order, or a cycle of calls, is a violation only if the
reference does not make it as well: a callback or an injected object calls
"upwards" in the reference too, and that is the design, not a breach of it.
"""

from __future__ import annotations

from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.dynamic.translation import NameTranslation
from pythonarchtesting.entities import Entity
from pythonarchtesting.execution.import_edges import (
    NormalizedImportEdge,
    collect_canonical_module_entities,
    collect_normalized_import_edges_for_modules,
)
from pythonarchtesting.execution.module_structure import (
    Edge,
    cycle_path,
    describe_violation,
    import_module_edges,
    layer_violations,
    parse_layers,
    rename_edges,
    strongly_connected,
)
from pythonarchtesting.matching import MatchResult

from .messages import _build_rule_result
from .runtime_structure import (
    _coverage,
    _coverage_note,
    _describe_call,
    _edges,
    _fold_new_modules,
    run_edges,
)

_MAX_REPORTED = 25


def _import_graph(rule: Rule, ctx: EvalContext) -> dict[Edge, NormalizedImportEdge]:
    modules = collect_canonical_module_entities(entities=ctx.target_index.all_sorted)
    internal = frozenset(entity.module_path for entity in modules)
    edges = collect_normalized_import_edges_for_modules(
        entities=modules, scope_modules=internal
    )
    return import_module_edges(
        edges,
        internal,
        ignore_type_checking=bool(rule.params.get("ignore_type_checking", True)),
    )


def _line(edge: NormalizedImportEdge | None) -> str:
    return f"{edge.filepath_rel}:{edge.lineno}" if edge is not None else "?"


def _steps(
    path: list[str] | tuple[str, ...], graph: dict[Edge, NormalizedImportEdge]
) -> list[dict[str, Any]]:
    steps = []
    for origin, target in zip(path, path[1:]):
        edge = graph.get((origin, target))
        steps.append(
            {
                "from": origin,
                "to": target,
                "filepath": edge.filepath_rel if edge else None,
                "lineno": edge.lineno if edge else None,
            }
        )
    return steps


def _finish(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    details: dict[str, Any],
    violations: list[str],
    passed: str,
) -> RuleResult:
    if not violations:
        details["reason"] = "no_violations"
        details["summary"] = passed
        return _build_rule_result(rule, source, target, match, "OK", details, ())
    details["violations"] = violations[:_MAX_REPORTED]
    details["violation_count"] = len(violations)
    details["reason"] = "violation"
    more = f" (+{len(violations) - 1} more)" if len(violations) > 1 else ""
    details["summary"] = violations[0] + more
    return _build_rule_result(rule, source, target, match, "FAILED", details, ())


class ModuleCyclesEvaluator:
    """Static ``forbid_cycles``: cycles in the target's import graph."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        graph = _import_graph(rule, ctx)
        cycles = []
        violations = []
        for component in strongly_connected(graph):
            path = cycle_path(component, graph)
            steps = _steps(path, graph)
            cycles.append({"modules": component, "path": path, "steps": steps})
            lines = ", ".join(f"{step['filepath']}:{step['lineno']}" for step in steps)
            violations.append(f"import cycle {' -> '.join(path)} ({lines})")
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "cycles": cycles[:_MAX_REPORTED],
        }
        modules = {module for pair in graph for module in pair}
        return _finish(
            rule,
            source,
            target,
            match,
            details,
            violations,
            f"no import cycle among {len(modules)} module(s)",
        )


class ModuleLayersEvaluator:
    """Static ``enforce_layers``: the layer order on the target's imports.

    Target modules are named by the reference modules they were matched to,
    so a renamed layer is still checked as that layer.
    """

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        layers = _layers(rule)
        names = NameTranslation.from_context(ctx)
        graph = rename_edges(
            _import_graph(rule, ctx), lambda module: names.source_module(module, "")
        )
        found = layer_violations(graph, layers, chains=True)
        violations = [
            f"{describe_violation(item)} ({_line(graph.get((item.path[0], item.path[1])))})"
            for item in found
        ]
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "layers": list(rule.params.get("layers") or []),
            "closed": list(rule.params.get("closed") or []),
            "paths": [
                {
                    "kind": item.kind,
                    "from_layer": item.origin_layer,
                    "to_layer": item.target_layer,
                    "steps": _steps(item.path, graph),
                }
                for item in found[:_MAX_REPORTED]
            ],
        }
        return _finish(
            rule,
            source,
            target,
            match,
            details,
            violations,
            f"imports follow the order of {len(layers)} layer(s)",
        )


def _layers(rule: Rule) -> list[Any]:
    return parse_layers(
        list(rule.params.get("layers") or []), list(rule.params.get("closed") or [])
    )


def _reference_modules(ctx: EvalContext) -> set[str]:
    return {str(entity.module_path) for entity in ctx.source_by_id.values()}


def _target_edges(
    case: dict[str, Any], names: NameTranslation, known: set[str]
) -> dict[Edge, dict[str, Any]]:
    """The case's module edges in reference names, new modules folded in."""
    return _fold_new_modules(_edges(case, names), known)


class _RuntimeStructureEvaluator:
    def _judge(
        self,
        rule: Rule,
        reference: list[dict[str, Any]],
        observed: list[dict[str, Any]],
        details: dict[str, Any],
    ) -> list[str]:
        raise NotImplementedError

    def _passed(self, rule: Rule, case_count: int) -> str:
        raise NotImplementedError

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        cases = list(rule.params.get("cases") or [])
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "case_count": len(cases),
            "entry": rule.params.get("entry"),
        }
        observed = run_edges(rule, source, target, ctx, details)
        if isinstance(observed, str):
            return _build_rule_result(
                rule, source, target, match, observed, details, ()
            )
        reference_cases, target_cases, names = observed
        known = _reference_modules(ctx)
        target_edges = [
            {"index": case.get("index"), "edges": _target_edges(case, names, known)}
            for case in target_cases
        ]
        violations = self._judge(rule, reference_cases, target_edges, details)
        coverage = _coverage(target_cases)
        if coverage is not None:
            details["coverage"] = coverage
        return _finish(
            rule,
            source,
            target,
            match,
            details,
            violations,
            self._passed(rule, len(cases)) + _coverage_note(coverage),
        )


def _reference_edges(reference: list[dict[str, Any]]) -> set[Edge]:
    return {pair for case in reference for pair in _edges(case)}


class RuntimeLayersEvaluator(_RuntimeStructureEvaluator):
    """Runtime ``enforce_layers``: the layer order on calls between modules.

    Only direct calls are judged (a call graph has no chains: two calls
    recorded in different contexts do not make a path), after a module the
    reference lacks has been folded into the modules that call it.
    """

    def _judge(
        self,
        rule: Rule,
        reference: list[dict[str, Any]],
        observed: list[dict[str, Any]],
        details: dict[str, Any],
    ) -> list[str]:
        layers = _layers(rule)
        allowed = _reference_edges(reference)
        details["layers"] = list(rule.params.get("layers") or [])
        details["closed"] = list(rule.params.get("closed") or [])
        details["reference_edges"] = sorted(f"{a} -> {b}" for a, b in allowed)
        violations: list[str] = []
        for case in observed:
            edges = case["edges"]
            for item in layer_violations(edges, layers, chains=False):
                pair = (item.path[0], item.path[-1])
                if pair in allowed:
                    continue  # the reference makes this call too
                violations.append(
                    f"case {case['index']}: {describe_violation(item)} "
                    f"({_describe_call(edges[pair])})"
                )
        return violations

    def _passed(self, rule: Rule, case_count: int) -> str:
        return f"calls followed the layer order in {case_count} case(s)"


class RuntimeCyclesEvaluator(_RuntimeStructureEvaluator):
    """Runtime ``forbid_cycles``: cycles of calls the reference does not have."""

    def _judge(
        self,
        rule: Rule,
        reference: list[dict[str, Any]],
        observed: list[dict[str, Any]],
        details: dict[str, Any],
    ) -> list[str]:
        reference_cycles = strongly_connected(_reference_edges(reference))
        details["reference_cycles"] = reference_cycles
        calls: dict[Edge, dict[str, Any]] = {}
        for case in observed:
            for pair, call in case["edges"].items():
                calls.setdefault(pair, call)
        violations: list[str] = []
        for component in strongly_connected(calls):
            if any(set(component) <= set(known) for known in reference_cycles):
                continue
            path = cycle_path(component, calls)
            steps = "; ".join(
                _describe_call(calls[(origin, target)])
                for origin, target in zip(path, path[1:])
            )
            violations.append(f"call cycle {' -> '.join(path)} ({steps})")
        return violations

    def _passed(self, rule: Rule, case_count: int) -> str:
        return f"no call cycle the reference lacks in {case_count} case(s)"


__all__ = [
    "ModuleCyclesEvaluator",
    "ModuleLayersEvaluator",
    "RuntimeCyclesEvaluator",
    "RuntimeLayersEvaluator",
]
