"""Module-level structure of a project: dependency cycles and layer order.

The static rules build the module graph from import statements, the runtime
rules from the calls one module made into another; both then ask the same
questions of it, answered here. A graph is a mapping from ``(from, to)``
module pairs to whatever first created the edge (an import statement, a
recorded call), so a finding can point at a line.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Collection, Iterable, Literal, Mapping, Sequence

from pythonarchtesting.execution.import_edges import NormalizedImportEdge

Edge = tuple[str, str]

_INDEPENDENT = "|"
_NOT_INDEPENDENT = ":"


def in_module(name: str, module: str) -> bool:
    """Whether ``name`` is ``module`` or lies inside it."""
    if not module:
        return name == module
    return name == module or name.startswith(module + ".")


def module_of(name: str, modules: Collection[str]) -> str | None:
    """The most specific module of ``modules`` that ``name`` is or lies in."""
    found = [module for module in modules if in_module(name, module)]
    return max(found, key=len) if found else None


def _sort_key(edge: NormalizedImportEdge) -> tuple[str, str, int, str]:
    return (edge.importer_module, edge.filepath_rel, edge.lineno, edge.imported_module)


def import_module_edges(
    edges: Iterable[NormalizedImportEdge],
    modules: Collection[str],
    *,
    ignore_type_checking: bool = True,
) -> dict[Edge, NormalizedImportEdge]:
    """Module-to-module edges between the project's ``modules``.

    Every import statement counts, at module level or inside a function, as
    in import-linter: a lazy import still makes the module depend on the
    other. An imported name resolves to the module it lies in
    (``models.Order`` -> ``models``). ``from pkg import sub`` of a submodule
    is an edge to ``pkg.sub`` only, not also to ``pkg``.
    """
    ordered = sorted(edges, key=_sort_key)
    statements: dict[tuple[str, str, int], set[str]] = {}
    for edge in ordered:
        key = (edge.importer_module, edge.filepath_rel, edge.lineno)
        statements.setdefault(key, set()).add(edge.imported_module)

    graph: dict[Edge, NormalizedImportEdge] = {}
    for edge in ordered:
        if ignore_type_checking and edge.in_type_checking:
            continue
        origin = edge.importer_module
        target = module_of(edge.imported_module, modules)
        if target is None or target == origin:
            continue
        if edge.imported_module == target:
            siblings = statements[(origin, edge.filepath_rel, edge.lineno)]
            if any(
                other.startswith(target + ".")
                and module_of(other, modules) not in (None, target)
                for other in siblings
            ):
                continue
        graph.setdefault((origin, target), edge)
    return graph


def strongly_connected(edges: Collection[Edge]) -> list[list[str]]:
    """Groups of two or more modules that all reach each other (cycles).

    Tarjan's algorithm, iterative so that a long chain of modules cannot
    exhaust the recursion limit. Each group is sorted, and so is the list.
    """
    adjacency: dict[str, list[str]] = {}
    for origin, target in sorted(edges):
        adjacency.setdefault(origin, []).append(target)
        adjacency.setdefault(target, [])

    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []
    counter = 0

    for root in sorted(adjacency):
        if root in index:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, position = work.pop()
            if position == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            successors = adjacency[node]
            if position < len(successors):
                work.append((node, position + 1))
                successor = successors[position]
                if successor not in index:
                    work.append((successor, 0))
                elif successor in on_stack:
                    low[node] = min(low[node], index[successor])
                continue
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    components.append(sorted(component))
    return sorted(components)


def cycle_path(component: Sequence[str], edges: Collection[Edge]) -> list[str]:
    """One shortest cycle through the first module of ``component``.

    Returned closed: ``["a", "b", "a"]``.
    """
    members = set(component)
    start = component[0]
    adjacency: dict[str, list[str]] = {}
    for origin, target in sorted(edges):
        if origin in members and target in members:
            adjacency.setdefault(origin, []).append(target)
    previous: dict[str, str] = {}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for successor in adjacency.get(node, []):
            if successor == start:
                path = [node]
                while path[-1] != start:
                    path.append(previous[path[-1]])
                return list(reversed(path)) + [start]
            if successor not in previous:
                previous[successor] = node
                queue.append(successor)
    return [start, start]


@dataclass(frozen=True)
class Layer:
    """One entry of a layer list: one module, or sibling modules side by side.

    No layer above a ``closed`` one may use a layer below it directly: its
    calls have to go through the closed layer.
    """

    modules: tuple[str, ...]
    independent: bool = True
    closed: bool = False


def parse_layers(raw: Sequence[str], closed: Sequence[str] = ()) -> list[Layer]:
    """Layers from import-linter's notation, highest first.

    ``"a | b"`` are independent siblings (neither may use the other),
    ``"a : b"`` siblings that may use each other. ``closed`` names layers,
    by any of their modules, that no higher layer may bypass.
    """
    layers: list[Layer] = []
    for entry in raw:
        if _INDEPENDENT in entry and _NOT_INDEPENDENT in entry:
            raise ValueError(f"layer {entry!r} mixes '|' and ':'")
        delimiter = _NOT_INDEPENDENT if _NOT_INDEPENDENT in entry else _INDEPENDENT
        modules = tuple(part.strip() for part in entry.split(delimiter))
        if not all(modules):
            raise ValueError(f"layer {entry!r} names an empty module")
        layers.append(
            Layer(
                modules,
                independent=delimiter == _INDEPENDENT,
                closed=any(module in closed for module in modules),
            )
        )
    named = [module for layer in layers for module in layer.modules]
    repeated = sorted({module for module in named if named.count(module) > 1})
    if repeated:
        raise ValueError(f"modules named in more than one layer: {repeated}")
    unknown = sorted(set(closed) - set(named))
    if unknown:
        raise ValueError(f"closed names modules that are in no layer: {unknown}")
    if layers and layers[-1].closed:
        raise ValueError("the lowest layer cannot be closed: nothing lies below it")
    return layers


ViolationKind = Literal["upward", "sibling", "skip"]


@dataclass(frozen=True)
class LayerViolation:
    """A path from one layer to another that the layer order forbids.

    ``kind`` is ``"upward"`` (a lower layer uses a higher one), ``"sibling"``
    (independent siblings use each other) or ``"skip"`` (a layer uses one
    below a closed layer, bypassing it; ``closed_layer`` names it). ``path``
    is the chain of modules, at least the two ends.
    """

    kind: ViolationKind
    origin_layer: str
    target_layer: str
    path: tuple[str, ...]
    closed_layer: str = ""


def _placement(module: str, layers: Sequence[Layer]) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None
    for position, layer in enumerate(layers):
        for member in layer.modules:
            if in_module(module, member) and (
                best is None or len(member) > len(best[1])
            ):
                best = (position, member)
    return best


def _kind(
    origin: tuple[int, str],
    target: tuple[int, str],
    layers: Sequence[Layer],
) -> tuple[ViolationKind, str] | None:
    if target[0] < origin[0]:
        return "upward", ""
    if target[0] == origin[0]:
        return ("sibling", "") if layers[origin[0]].independent else None
    for between in layers[origin[0] + 1 : target[0]]:
        if between.closed:
            return "skip", " | ".join(between.modules)
    return None


def layer_violations(
    edges: Collection[Edge],
    layers: Sequence[Layer],
    *,
    chains: bool = True,
) -> list[LayerViolation]:
    """Paths between layered modules that break the layer order.

    A higher layer may use a lower one; the reverse is a violation, and so
    is a use between independent siblings, and one that bypasses a closed
    layer. With ``chains`` a path through
    modules no layer names counts too (``repository -> helpers ->
    controller``), as in import-linter; a path is never followed through
    another layer, whose own edges are judged on their own. Each pair of
    modules is reported once, by its shortest path.
    """
    adjacency: dict[str, list[str]] = {}
    for origin, target in sorted(edges):
        adjacency.setdefault(origin, []).append(target)

    found: list[LayerViolation] = []
    for start in sorted(adjacency):
        start_place = _placement(start, layers)
        if start_place is None:
            continue
        previous: dict[str, str] = {start: start}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for successor in adjacency.get(node, []):
                if successor in previous:
                    continue
                previous[successor] = node
                place = _placement(successor, layers)
                if place is not None and place[1] == start_place[1]:
                    queue.append(successor)  # inside the start's own layer module
                    continue
                if place is None:
                    if chains:
                        queue.append(successor)
                    continue
                verdict = _kind(start_place, place, layers)
                if verdict is None:
                    continue
                path = [successor]
                while path[-1] != start:
                    path.append(previous[path[-1]])
                found.append(
                    LayerViolation(
                        kind=verdict[0],
                        origin_layer=start_place[1],
                        target_layer=place[1],
                        path=tuple(reversed(path)),
                        closed_layer=verdict[1],
                    )
                )
    return sorted(found, key=lambda item: (item.path, item.kind))


def describe_violation(violation: LayerViolation) -> str:
    chain = " -> ".join(violation.path)
    if violation.kind == "upward":
        return (
            f"{chain}: {violation.origin_layer} is below "
            f"{violation.target_layer} and must not use it"
        )
    if violation.kind == "sibling":
        return (
            f"{chain}: {violation.origin_layer} and {violation.target_layer} "
            "are independent siblings"
        )
    return (
        f"{chain}: {violation.origin_layer} bypasses the closed layer "
        f"{violation.closed_layer} to reach {violation.target_layer}"
    )


def rename_edges(edges: Mapping[Edge, Any], rename: Any) -> dict[Edge, Any]:
    """``edges`` with both ends renamed by ``rename(module)``.

    Edges that become a loop (two modules renamed to one) are dropped; the
    first edge of each renamed pair is kept.
    """
    renamed: dict[Edge, Any] = {}
    for (origin, target), value in edges.items():
        pair = (rename(origin), rename(target))
        if pair[0] != pair[1]:
            renamed.setdefault(pair, value)
    return renamed


__all__ = [
    "Edge",
    "Layer",
    "LayerViolation",
    "cycle_path",
    "describe_violation",
    "import_module_edges",
    "in_module",
    "layer_violations",
    "module_of",
    "parse_layers",
    "rename_edges",
    "strongly_connected",
]
