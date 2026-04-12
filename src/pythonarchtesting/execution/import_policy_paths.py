from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from pythonarchtesting.execution.import_graph import ModuleDependencyGraph

MAX_REPORTED_REACHABLE_PATHS = 25


@dataclass(frozen=True)
class ImportPathStep:
    from_module: str
    to_module: str
    filepath_rel: str
    lineno: int
    in_type_checking: bool
    is_top_level: bool


@dataclass(frozen=True)
class ReachableImportViolation:
    start_module: str
    forbidden_target: str
    forbidden_prefix: str
    steps: tuple[ImportPathStep, ...]


def _matches_prefix(name: str, prefixes: Sequence[str]) -> str | None:
    for prefix in prefixes:
        if name == prefix or name.startswith(prefix + "."):
            return prefix
    return None


def _step_from_edge(
    *,
    from_module: str,
    to_module: str,
    filepath_rel: str,
    lineno: int,
    in_type_checking: bool,
    is_top_level: bool,
) -> ImportPathStep:
    return ImportPathStep(
        from_module=from_module,
        to_module=to_module,
        filepath_rel=filepath_rel,
        lineno=lineno,
        in_type_checking=in_type_checking,
        is_top_level=is_top_level,
    )


def _step_sort_key(
    step: ImportPathStep,
) -> tuple[str, str, str, int, bool, bool]:
    return (
        step.from_module,
        step.to_module,
        step.filepath_rel,
        step.lineno,
        step.in_type_checking,
        step.is_top_level,
    )


def _violation_sort_key(
    violation: ReachableImportViolation,
) -> tuple[str, str, tuple[tuple[str, str, str, int, bool, bool], ...]]:
    return (
        violation.start_module,
        violation.forbidden_target,
        tuple(_step_sort_key(step) for step in violation.steps),
    )


def collect_reachable_import_violations(
    *,
    graph: ModuleDependencyGraph,
    root_modules: Iterable[str],
    forbidden_prefixes: Sequence[str],
    allowed_prefixes: Sequence[str],
) -> tuple[ReachableImportViolation, ...]:
    violations: list[ReachableImportViolation] = []
    seen_violations: set[
        tuple[str, str, str, tuple[tuple[str, str, str, int, bool, bool], ...]]
    ] = set()

    def visit_module(
        *,
        start_module: str,
        current_module: str,
        path_steps: tuple[ImportPathStep, ...],
        path_modules: frozenset[str],
    ) -> None:
        for edge in graph.get_outgoing(current_module):
            if _matches_prefix(edge.imported_module, allowed_prefixes) is not None:
                continue

            step = _step_from_edge(
                from_module=edge.importer_module,
                to_module=edge.imported_module,
                filepath_rel=edge.filepath_rel,
                lineno=edge.lineno,
                in_type_checking=edge.in_type_checking,
                is_top_level=edge.is_top_level,
            )
            next_steps = path_steps + (step,)

            matched_forbidden = _matches_prefix(
                edge.imported_module, forbidden_prefixes
            )
            if matched_forbidden is not None:
                violation = ReachableImportViolation(
                    start_module=start_module,
                    forbidden_target=edge.imported_module,
                    forbidden_prefix=matched_forbidden,
                    steps=next_steps,
                )
                signature = (
                    violation.start_module,
                    violation.forbidden_target,
                    violation.forbidden_prefix,
                    tuple(_step_sort_key(item) for item in violation.steps),
                )
                if signature not in seen_violations:
                    seen_violations.add(signature)
                    violations.append(violation)
                continue

            imported_node = graph.nodes.get(edge.imported_module)
            if imported_node is None or not imported_node.is_internal:
                continue
            if edge.imported_module in path_modules:
                continue

            visit_module(
                start_module=start_module,
                current_module=edge.imported_module,
                path_steps=next_steps,
                path_modules=path_modules | {edge.imported_module},
            )

    for root_module in sorted(set(root_modules)):
        root_node = graph.nodes.get(root_module)
        if root_node is None or not root_node.is_internal:
            continue
        visit_module(
            start_module=root_module,
            current_module=root_module,
            path_steps=(),
            path_modules=frozenset({root_module}),
        )

    return tuple(sorted(violations, key=_violation_sort_key))


__all__: list[str] = []
