from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from pythonarchtesting.execution.import_edges import NormalizedImportEdge


@dataclass(frozen=True)
class ModuleNode:
    module_path: str
    filepath_rel: str | None = None
    is_internal: bool = True


@dataclass
class ModuleDependencyGraph:
    nodes: dict[str, ModuleNode] = field(default_factory=dict)
    outgoing_edges: dict[str, list[NormalizedImportEdge]] = field(default_factory=dict)

    def add_node(self, node: ModuleNode) -> None:
        existing = self.nodes.get(node.module_path)
        if existing is None:
            self.nodes[node.module_path] = node
            return

        filepath_rel = existing.filepath_rel or node.filepath_rel
        is_internal = existing.is_internal or node.is_internal
        self.nodes[node.module_path] = ModuleNode(
            module_path=node.module_path,
            filepath_rel=filepath_rel,
            is_internal=is_internal,
        )

    def add_edge(self, edge: NormalizedImportEdge) -> None:
        if edge.importer_module not in self.nodes:
            self.add_node(
                ModuleNode(
                    module_path=edge.importer_module,
                    filepath_rel=edge.filepath_rel,
                    is_internal=False,
                )
            )
        if edge.imported_module not in self.nodes:
            self.add_node(
                ModuleNode(
                    module_path=edge.imported_module,
                    filepath_rel=None,
                    is_internal=False,
                )
            )
        self.outgoing_edges.setdefault(edge.importer_module, []).append(edge)

    def get_outgoing(self, module_path: str) -> tuple[NormalizedImportEdge, ...]:
        return tuple(self.outgoing_edges.get(module_path, ()))


def _edge_sort_key(
    edge: NormalizedImportEdge,
) -> tuple[str, int, str, bool, bool]:
    return (
        edge.filepath_rel,
        edge.lineno,
        edge.imported_module,
        edge.in_type_checking,
        edge.is_top_level,
    )


def _sort_outgoing_edges(graph: ModuleDependencyGraph) -> None:
    for module_path, edges in list(graph.outgoing_edges.items()):
        graph.outgoing_edges[module_path] = sorted(edges, key=_edge_sort_key)


def build_module_dependency_graph(
    *,
    internal_modules: Mapping[str, str | None],
    edges: list[NormalizedImportEdge],
) -> ModuleDependencyGraph:
    graph = ModuleDependencyGraph()
    for module_path in sorted(internal_modules):
        graph.add_node(
            ModuleNode(
                module_path=module_path,
                filepath_rel=internal_modules[module_path],
                is_internal=True,
            )
        )

    seen_edges: set[NormalizedImportEdge] = set()
    for edge in edges:
        if edge in seen_edges:
            continue
        seen_edges.add(edge)
        graph.add_edge(edge)

    _sort_outgoing_edges(graph)
    return graph


def filter_module_dependency_graph(
    graph: ModuleDependencyGraph,
    *,
    ignore_type_checking: bool,
    include_local_edges: bool,
    ignored_filepaths: set[str] | None = None,
) -> ModuleDependencyGraph:
    ignored = ignored_filepaths or set()
    externalized_modules = {
        module_path
        for module_path, node in graph.nodes.items()
        if node.is_internal and node.filepath_rel in ignored
    }

    filtered = ModuleDependencyGraph()
    for module_path in sorted(graph.nodes):
        node = graph.nodes[module_path]
        filtered.add_node(
            ModuleNode(
                module_path=module_path,
                filepath_rel=node.filepath_rel,
                is_internal=node.is_internal
                and module_path not in externalized_modules,
            )
        )

    for module_path in sorted(graph.outgoing_edges):
        for edge in graph.outgoing_edges[module_path]:
            if edge.filepath_rel in ignored:
                continue
            if ignore_type_checking and edge.in_type_checking:
                continue
            if not include_local_edges and not edge.is_top_level:
                continue
            filtered.add_edge(edge)

    _sort_outgoing_edges(filtered)
    return filtered


__all__: list[str] = []
