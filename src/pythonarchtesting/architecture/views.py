"""Views of a model comparison for reports (F3.2–F3.5).

``architecture_entry`` leaves its comparison as ``{layer: {kind: [edge]}}``
(``EdgeDiff.to_dict``). These functions derive what a reader looks at from
it, without judging anything again:

- a dependency structure matrix of one layer (``matrix``);
- the target's edges seen only statically or only at run time
  (``static_runtime``);
- fan-in, fan-out and instability per module (``metrics``), informative
  only: coupling numbers do not tell whether the intended structure holds;
- the edges many targets of a run share (``aggregate``), where an edge most
  of a class diverges on points at the model rather than at the students.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pythonarchtesting.execution.module_structure import Edge

from .compare import class_module, parse_edge

Diff = Mapping[str, Sequence[str]]

# Edges the reference has, and edges the target has, in a layer's diff.
# ``reference`` lists them all; a diff without it (from before it existed)
# falls back to ``convergent`` + ``absent``, which misses a reference edge
# an exception put among ``allowed`` or ``divergent``.
REFERENCE = ("reference",)
REFERENCE_KINDS = ("convergent", "absent")
TARGET_KINDS = ("convergent", "divergent", "undecided", "allowed")
# Layers whose edges join two modules of the program (``external`` joins a
# module and a library).
INTERNAL_LAYERS = ("imports", "calls", "instances")
STATIC_LAYERS = ("imports",)
RUNTIME_LAYERS = ("calls", "instances")
SYMBOLS = {
    "convergent": "=",
    "divergent": "+",
    "absent": "-",
    "undecided": "?",
    "allowed": "a",
}
AGGREGATED_KINDS = ("divergent", "absent", "undecided")
# Matrix cells, least to most in need of a reader: a later kind wins a cell
# several objects of one module share.
_CELL_ORDER = ("convergent", "allowed", "absent", "undecided", "divergent")


def _parsed(texts: Iterable[str]) -> Iterator[Edge]:
    for text in texts:
        try:
            yield parse_edge(text)
        except ValueError:
            continue


def program_modules(architecture: Mapping[str, Diff] | None) -> set[str]:
    """The modules the comparison names, from its module-to-module layers."""
    found: set[str] = set()
    for layer, diff in (architecture or {}).items():
        if layer not in INTERNAL_LAYERS:
            continue
        for texts in (diff or {}).values():
            for origin, end in _parsed(texts or []):
                found.add(origin)
                if layer != "instances":
                    found.add(end)
    return found


def _module_level(layer: str, edge: Edge, modules: Collection[str]) -> Edge:
    """An ``instances`` edge ends in a class (``"module.Qual.Name"``): use its module."""
    if layer != "instances":
        return edge
    return edge[0], class_module(edge[1], modules) or "__init__"


def edges_of(
    diff: Diff | None,
    kinds: Iterable[str],
    layer: str = "",
    modules: Collection[str] = (),
) -> set[Edge]:
    """The parsed edges of ``kinds`` in a layer's diff, between modules.

    Malformed edges are skipped; an object's class is named by its module,
    the longest of ``modules`` that prefixes it.
    """
    kinds = tuple(kinds)
    if kinds == REFERENCE and diff is not None and "reference" not in diff:
        kinds = REFERENCE_KINDS
    found: set[Edge] = set()
    for kind in kinds:
        for edge in _parsed((diff or {}).get(kind) or []):
            found.add(_module_level(layer, edge, modules))
    return found


def layers_edges(
    architecture: Mapping[str, Diff], layers: Iterable[str], kinds: Iterable[str]
) -> set[Edge]:
    kinds = tuple(kinds)
    modules = program_modules(architecture)
    found: set[Edge] = set()
    for layer in layers:
        found |= edges_of(architecture.get(layer), kinds, layer, modules)
    return found


@dataclass(frozen=True)
class Matrix:
    """A layer as a matrix: ``cells[(origin, end)]`` is the edge's symbol."""

    modules: tuple[str, ...]
    cells: dict[Edge, str]


def matrix(
    diff: Diff | None,
    layer: str = "",
    architecture: Mapping[str, Diff] | None = None,
) -> Matrix:
    """The dependency structure matrix of one layer (rows use columns).

    Several objects of one module make one cell; the kind that most needs a
    reader wins (divergent, then undecided, absent, allowed, convergent).
    ``architecture`` names the program's modules for nested classes.
    """
    modules = program_modules(architecture)
    cells: dict[Edge, str] = {}
    for kind in _CELL_ORDER:
        for edge in edges_of(diff, (kind,), layer, modules):
            cells[edge] = SYMBOLS[kind]
    return Matrix(
        modules=tuple(sorted({module for edge in cells for module in edge})),
        cells=cells,
    )


@dataclass(frozen=True)
class StaticRuntime:
    """The target's edges by where they show: imports against calls and objects."""

    static_only: tuple[Edge, ...]
    runtime_only: tuple[Edge, ...]
    both: int
    # Of each list, the edges the reference shows the same way: a dependency
    # that is static only (or run time only) by design, e.g. an injected
    # collaborator.
    reference_static_only: frozenset[Edge]
    reference_runtime_only: frozenset[Edge]


def static_runtime(
    static: Mapping[str, Diff], runtime: Mapping[str, Diff]
) -> StaticRuntime:
    """Compare the target's import edges with the edges it shows at run time.

    An edge only imported may be a dead import, one used only for
    annotations, or one the cases did not exercise. An edge only seen at run
    time comes without an import: an injected object, a computed import, a
    callback.
    """
    imported = layers_edges(static, STATIC_LAYERS, TARGET_KINDS)
    used = layers_edges(runtime, RUNTIME_LAYERS, TARGET_KINDS)
    ref_imported = layers_edges(static, STATIC_LAYERS, REFERENCE)
    ref_used = layers_edges(runtime, RUNTIME_LAYERS, REFERENCE)
    return StaticRuntime(
        static_only=tuple(sorted(imported - used)),
        runtime_only=tuple(sorted(used - imported)),
        both=len(imported & used),
        reference_static_only=frozenset(ref_imported - ref_used),
        reference_runtime_only=frozenset(ref_used - ref_imported),
    )


@dataclass(frozen=True)
class ModuleMetrics:
    fan_in: int
    fan_out: int

    @property
    def instability(self) -> float | None:
        """Fan-out over all couplings (Martin's I); ``None`` for an isolated module."""
        total = self.fan_in + self.fan_out
        return self.fan_out / total if total else None


def metrics(edges: Iterable[Edge]) -> dict[str, ModuleMetrics]:
    """Fan-in and fan-out per module: distinct modules using it and it uses."""
    users: dict[str, set[str]] = {}
    used: dict[str, set[str]] = {}
    for origin, end in edges:
        if origin == end:
            continue
        used.setdefault(origin, set()).add(end)
        users.setdefault(end, set()).add(origin)
        users.setdefault(origin, set())
        used.setdefault(end, set())
    return {
        module: ModuleMetrics(fan_in=len(users[module]), fan_out=len(used[module]))
        for module in sorted(users)
    }


@dataclass(frozen=True)
class SharedEdge:
    rule: str
    layer: str
    kind: str
    edge: str
    targets: int
    of: int

    @property
    def share(self) -> float:
        return self.targets / self.of if self.of else 0.0


def aggregate(
    per_target: Iterable[Mapping[str, Mapping[str, Diff]]],
    kinds: Sequence[str] = AGGREGATED_KINDS,
) -> list[SharedEdge]:
    """Edges by how many targets share them, most shared first.

    ``per_target`` holds, for each target, ``{rule: architecture}``; a rule
    counts the targets that carry its comparison.
    """
    counts: dict[tuple[str, str, str, str], int] = {}
    carried: dict[str, int] = {}
    for rules in per_target:
        for rule, architecture in rules.items():
            carried[rule] = carried.get(rule, 0) + 1
            for layer, diff in architecture.items():
                for kind in kinds:
                    for edge in set((diff or {}).get(kind) or []):
                        key = (rule, layer, kind, str(edge))
                        counts[key] = counts.get(key, 0) + 1
    shared = [
        SharedEdge(rule, layer, kind, edge, count, carried[rule])
        for (rule, layer, kind, edge), count in counts.items()
    ]
    return sorted(
        shared, key=lambda s: (-s.share, -s.targets, s.rule, s.layer, s.kind, s.edge)
    )


def architectures(results: Iterable[Any]) -> dict[str, dict[str, Any]]:
    """``{rule code: details.architecture}`` of the results that carry one."""
    found: dict[str, dict[str, Any]] = {}
    for result in results:
        details = getattr(result, "details", None) or {}
        architecture = (
            details.get("architecture") if isinstance(details, dict) else None
        )
        if isinstance(architecture, dict) and architecture:
            found[str(result.rule_id).split("/")[0]] = architecture
    return found


__all__ = [
    "AGGREGATED_KINDS",
    "INTERNAL_LAYERS",
    "REFERENCE",
    "Matrix",
    "ModuleMetrics",
    "SYMBOLS",
    "SharedEdge",
    "StaticRuntime",
    "aggregate",
    "architectures",
    "edges_of",
    "layers_edges",
    "matrix",
    "metrics",
    "program_modules",
    "static_runtime",
]
