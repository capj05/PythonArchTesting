from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Iterable

from pythonarchtesting.entities import DeclarationEntry, Entity
from pythonarchtesting.rules.compilation.declarations import (
    is_invalid_annotation_declaration,
    normalize_declaration_entries,
)


@dataclass(frozen=True)
class FlowMarker:
    stage: str
    variable: str
    anchor_lineno: int
    anchor_col: int
    anchor_kind: str
    statement_order: int


@dataclass
class CfgNode:
    node_id: int
    lineno: int
    col: int
    kind: str
    successors: list[int] = field(default_factory=list)
    flow_markers: list[FlowMarker] = field(default_factory=list)


@dataclass(frozen=True)
class FunctionCfg:
    entry_node_id: int | None
    nodes: dict[int, CfgNode]


def flow_declarations_for_entity(
    entity: Entity,
    *,
    variable: str | None = None,
) -> list[DeclarationEntry]:
    entries = [
        entry
        for entry in normalize_declaration_entries(entity)
        if entry.kind == "flow"
        and entry.surface == "statement"
        and not is_invalid_annotation_declaration(entry)
    ]
    if variable is not None:
        entries = [
            entry for entry in entries if entry.params.get("variable") == variable
        ]
    return entries


def build_function_cfg(entity: Entity, *, variable: str | None = None) -> FunctionCfg:
    node = entity.extras.get("ast_node")
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return FunctionCfg(entry_node_id=None, nodes={})

    flow_by_anchor: dict[tuple[int, int], list[FlowMarker]] = {}
    for entry in flow_declarations_for_entity(entity, variable=variable):
        stage = entry.params.get("stage")
        flow_variable = entry.params.get("variable")
        if not isinstance(stage, str) or not isinstance(flow_variable, str):
            continue
        marker = FlowMarker(
            stage=stage,
            variable=flow_variable,
            anchor_lineno=int(entry.params.get("anchor_lineno", 0) or 0),
            anchor_col=int(entry.params.get("anchor_col", 0) or 0),
            anchor_kind=str(entry.params.get("anchor_kind", "")),
            statement_order=int(entry.params.get("statement_order", 0) or 0),
        )
        flow_by_anchor.setdefault((marker.anchor_lineno, marker.anchor_col), []).append(
            marker
        )

    builder = _CfgBuilder(flow_by_anchor)
    entry_id, _ = builder.build_block(node.body)
    return FunctionCfg(entry_node_id=entry_id, nodes=builder.nodes)


class _CfgBuilder:
    def __init__(self, flow_by_anchor: dict[tuple[int, int], list[FlowMarker]]) -> None:
        self.flow_by_anchor = flow_by_anchor
        self.nodes: dict[int, CfgNode] = {}
        self.next_node_id = 0

    def _new_node(self, stmt: ast.stmt, kind: str) -> int:
        node_id = self.next_node_id
        self.next_node_id += 1
        flow_markers = sorted(
            self.flow_by_anchor.get(
                (getattr(stmt, "lineno", 0), getattr(stmt, "col_offset", 0)),
                [],
            ),
            key=lambda item: (
                item.statement_order,
                item.anchor_lineno,
                item.anchor_col,
            ),
        )
        self.nodes[node_id] = CfgNode(
            node_id=node_id,
            lineno=getattr(stmt, "lineno", 0),
            col=getattr(stmt, "col_offset", 0),
            kind=kind,
            flow_markers=flow_markers,
        )
        return node_id

    def build_block(
        self, statements: Iterable[ast.stmt]
    ) -> tuple[int | None, list[int]]:
        entry_id: int | None = None
        pending: list[int] = []
        for stmt in statements:
            stmt_entry, stmt_exits = self.build_stmt(stmt)
            if stmt_entry is None:
                continue
            if entry_id is None:
                entry_id = stmt_entry
            for node_id in pending:
                if self.nodes[node_id].kind == "Return":
                    continue
                self.nodes[node_id].successors.append(stmt_entry)
            pending = stmt_exits
        return entry_id, pending

    def build_stmt(self, stmt: ast.stmt) -> tuple[int | None, list[int]]:
        if isinstance(stmt, ast.Return):
            node_id = self._new_node(stmt, "Return")
            return node_id, [node_id]

        if isinstance(stmt, ast.If):
            node_id = self._new_node(stmt, "If")
            body_entry, body_exits = self.build_block(stmt.body)
            else_entry, else_exits = self.build_block(stmt.orelse)
            if body_entry is not None:
                self.nodes[node_id].successors.append(body_entry)
            if else_entry is not None:
                self.nodes[node_id].successors.append(else_entry)
            if_exits: list[int] = []
            if_exits.extend(body_exits or ([node_id] if body_entry is None else []))
            if_exits.extend(else_exits or ([node_id] if else_entry is None else []))
            if else_entry is None and not stmt.orelse:
                if_exits.append(node_id)
            return node_id, if_exits

        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            node_id = self._new_node(stmt, type(stmt).__name__)
            body_entry, body_exits = self.build_block(stmt.body)
            orelse_entry, orelse_exits = self.build_block(stmt.orelse)
            if body_entry is not None:
                self.nodes[node_id].successors.append(body_entry)
                for exit_id in body_exits:
                    if self.nodes[exit_id].kind == "Return":
                        continue
                    self.nodes[exit_id].successors.append(node_id)
            if orelse_entry is not None:
                self.nodes[node_id].successors.append(orelse_entry)
                return node_id, orelse_exits
            return node_id, [node_id]

        if isinstance(stmt, ast.Try):
            node_id = self._new_node(stmt, "Try")
            body_entry, body_exits = self.build_block(stmt.body)
            if body_entry is not None:
                self.nodes[node_id].successors.append(body_entry)
            handler_exits: list[int] = []
            for handler in stmt.handlers:
                handler_entry, current_handler_exits = self.build_block(handler.body)
                if handler_entry is not None:
                    self.nodes[node_id].successors.append(handler_entry)
                handler_exits.extend(current_handler_exits)
            orelse_entry, orelse_exits = self.build_block(stmt.orelse)
            if orelse_entry is not None:
                for exit_id in body_exits:
                    if self.nodes[exit_id].kind == "Return":
                        continue
                    self.nodes[exit_id].successors.append(orelse_entry)
                normal_exits = orelse_exits
            else:
                normal_exits = body_exits
            combined_exits = [*normal_exits, *handler_exits]
            if stmt.finalbody:
                finally_entry, finally_exits = self.build_block(stmt.finalbody)
                if finally_entry is not None:
                    for exit_id in combined_exits:
                        if self.nodes[exit_id].kind == "Return":
                            continue
                        self.nodes[exit_id].successors.append(finally_entry)
                    return node_id, finally_exits
            return node_id, combined_exits or [node_id]

        if isinstance(stmt, ast.Match):
            node_id = self._new_node(stmt, "Match")
            match_exits: list[int] = []
            for case in stmt.cases:
                case_entry, case_exits = self.build_block(case.body)
                if case_entry is not None:
                    self.nodes[node_id].successors.append(case_entry)
                match_exits.extend(case_exits)
            return node_id, match_exits or [node_id]

        if isinstance(stmt, (ast.With, ast.AsyncWith)):
            node_id = self._new_node(stmt, type(stmt).__name__)
            body_entry, body_exits = self.build_block(stmt.body)
            if body_entry is not None:
                self.nodes[node_id].successors.append(body_entry)
                return node_id, body_exits
            return node_id, [node_id]

        node_id = self._new_node(stmt, type(stmt).__name__)
        return node_id, [node_id]


__all__ = [
    "CfgNode",
    "FlowMarker",
    "FunctionCfg",
    "build_function_cfg",
    "flow_declarations_for_entity",
]
