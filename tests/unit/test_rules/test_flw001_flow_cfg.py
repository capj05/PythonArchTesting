"""Structure of the control-flow graph that FLW001 (``enforce_flow``) walks.

Nodes are labelled ``Kind@line``; the function header is line 1, so the body
starts on line 2.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.execution.flow_cfg import FunctionCfg, build_function_cfg


def _cfg(body: str, *, header: str = "def process(value, items):") -> FunctionCfg:
    source = header + "\n" + textwrap.indent(textwrap.dedent(body).lstrip("\n"), "    ")
    for entity in extract_entities_from_source(
        source_text=source,
        file_path=Path("target_module.py"),
        root_path=Path("."),
        target_module_name=None,
        role="target",
        include_nested_functions=False,
        root_label="target",
    ):
        if entity.kind == "function" and entity.name == "process":
            return build_function_cfg(entity)
    raise AssertionError("function 'process' not found")


def _label(cfg: FunctionCfg, node_id: int) -> str:
    node = cfg.nodes[node_id]
    return f"{node.kind}@{node.lineno}"


def _edges(cfg: FunctionCfg) -> dict[str, list[str]]:
    return {
        _label(cfg, node_id): [_label(cfg, succ) for succ in node.successors]
        for node_id, node in cfg.nodes.items()
    }


def _function_exits(cfg: FunctionCfg) -> set[str]:
    return {_label(cfg, node_id) for node_id in cfg.exit_node_ids}


# --- If ---------------------------------------------------------------------


def test_if_without_else_links_the_header_to_the_next_statement_once() -> None:
    cfg = _cfg("""
        if value:
            value = 1
        return value
        """)
    assert _edges(cfg) == {
        "If@2": ["Assign@3", "Return@4"],
        "Assign@3": ["Return@4"],
        "Return@4": [],
    }


def test_if_without_else_at_the_end_of_the_function_exits_from_the_header() -> None:
    cfg = _cfg("""
        if value:
            value = 1
        """)
    assert _edges(cfg) == {"If@2": ["Assign@3"], "Assign@3": []}
    assert _function_exits(cfg) == {"If@2", "Assign@3"}


def test_returns_and_the_last_statement_are_function_exits() -> None:
    cfg = _cfg("""
        if value:
            return value
        value = 1
        """)
    assert _function_exits(cfg) == {"Return@3", "Assign@4"}


# --- loops ------------------------------------------------------------------


def test_loop_at_the_end_of_the_function_exits_from_the_header() -> None:
    cfg = _cfg("""
        for item in items:
            value = item
        """)
    assert _edges(cfg) == {"For@2": ["Assign@3"], "Assign@3": ["For@2"]}
    assert _function_exits(cfg) == {"For@2"}


def test_break_leaves_the_loop() -> None:
    cfg = _cfg("""
        for item in items:
            if item:
                break
            value = item
        return value
        """)
    assert _edges(cfg) == {
        "For@2": ["If@3", "Return@6"],
        "If@3": ["Break@4", "Assign@5"],
        "Break@4": ["Return@6"],
        "Assign@5": ["For@2"],
        "Return@6": [],
    }


def test_break_skips_the_loop_else() -> None:
    cfg = _cfg("""
        for item in items:
            if item:
                break
        else:
            value = 1
        return value
        """)
    assert _edges(cfg) == {
        "For@2": ["If@3", "Assign@6"],
        "If@3": ["Break@4", "For@2"],
        "Break@4": ["Return@7"],
        "Assign@6": ["Return@7"],
        "Return@7": [],
    }


def test_while_else_runs_only_when_the_condition_fails() -> None:
    cfg = _cfg("""
        while value:
            if items:
                break
            value = value - 1
        else:
            value = 0
        return value
        """)
    assert _edges(cfg) == {
        "While@2": ["If@3", "Assign@7"],
        "If@3": ["Break@4", "Assign@5"],
        "Break@4": ["Return@8"],
        "Assign@5": ["While@2"],
        "Assign@7": ["Return@8"],
        "Return@8": [],
    }


def test_continue_returns_to_the_loop_header() -> None:
    cfg = _cfg("""
        for item in items:
            if not item:
                continue
            value = item
        return value
        """)
    assert _edges(cfg) == {
        "For@2": ["If@3", "Return@6"],
        "If@3": ["Continue@4", "Assign@5"],
        "Continue@4": ["For@2"],
        "Assign@5": ["For@2"],
        "Return@6": [],
    }


def test_statements_after_break_or_continue_are_unreachable() -> None:
    cfg = _cfg("""
        for item in items:
            continue
            value = item
        return value
        """)
    edges = _edges(cfg)
    assert edges["Continue@3"] == ["For@2"]
    assert all("Assign@4" not in successors for successors in edges.values())


def test_break_belongs_to_the_innermost_loop() -> None:
    cfg = _cfg("""
        for item in items:
            for char in item:
                if char:
                    break
            value = item
        return value
        """)
    assert _edges(cfg) == {
        "For@2": ["For@3", "Return@7"],
        "For@3": ["If@4", "Assign@6"],
        "If@4": ["Break@5", "For@3"],
        "Break@5": ["Assign@6"],
        "Assign@6": ["For@2"],
        "Return@7": [],
    }


def test_break_in_a_loop_else_leaves_the_enclosing_loop() -> None:
    cfg = _cfg("""
        for item in items:
            for char in item:
                value = char
            else:
                break
        return value
        """)
    edges = _edges(cfg)
    assert edges["Break@6"] == ["Return@7"]
    assert edges["For@2"] == ["For@3", "Return@7"]


def test_while_true_leaves_only_through_break() -> None:
    cfg = _cfg("""
        while True:
            value = 1
            if value:
                break
        return value
        """)
    assert _edges(cfg) == {
        "While@2": ["Assign@3"],
        "Assign@3": ["If@4"],
        "If@4": ["Break@5", "While@2"],
        "Break@5": ["Return@6"],
        "Return@6": [],
    }


def test_async_for_handles_break_like_for() -> None:
    cfg = _cfg(
        """
        async for item in items:
            break
        return value
        """,
        header="async def process(value, items):",
    )
    assert _edges(cfg) == {
        "AsyncFor@2": ["Break@3", "Return@4"],
        "Break@3": ["Return@4"],
        "Return@4": [],
    }


def test_break_inside_try_finally_skips_the_finally_block() -> None:
    """Documented simplification: break/continue/return jump straight to their
    target; the ``finally`` block is not inserted on that path."""
    cfg = _cfg("""
        for item in items:
            try:
                break
            finally:
                value = 1
        return value
        """)
    assert _edges(cfg)["Break@4"] == ["Return@7"]


# --- Try / Match --------------------------------------------------------------


def test_try_except_else_finally_structure() -> None:
    cfg = _cfg("""
        try:
            value = 1
        except ValueError:
            value = 2
        else:
            value = 3
        finally:
            value = 4
        return value
        """)
    assert _edges(cfg) == {
        "Try@2": ["Assign@3", "Assign@5"],
        "Assign@3": ["Assign@7"],
        "Assign@5": ["Assign@9"],
        "Assign@7": ["Assign@9"],
        "Assign@9": ["Return@10"],
        "Return@10": [],
    }


def test_return_inside_try_does_not_pass_through_finally() -> None:
    cfg = _cfg("""
        try:
            return value
        finally:
            value = 1
        """)
    assert _edges(cfg) == {
        "Try@2": ["Return@3"],
        "Return@3": [],
        "Assign@5": [],
    }


def test_match_links_the_subject_to_every_case() -> None:
    cfg = _cfg("""
        match value:
            case 1:
                value = 1
            case _:
                value = 2
        return value
        """)
    assert _edges(cfg) == {
        "Match@2": ["Assign@4", "Assign@6"],
        "Assign@4": ["Return@7"],
        "Assign@6": ["Return@7"],
        "Return@7": [],
    }


def test_match_without_an_irrefutable_case_falls_through_past_the_match() -> None:
    """A subject that matches no case continues after the ``match``."""
    cfg = _cfg("""
        match value:
            case 1:
                value = 1
        return value
        """)
    assert _edges(cfg) == {
        "Match@2": ["Assign@4", "Return@5"],
        "Assign@4": ["Return@5"],
        "Return@5": [],
    }


def test_match_without_an_irrefutable_case_at_the_end_is_a_function_exit() -> None:
    cfg = _cfg("""
        match value:
            case 1:
                return value
        """)
    assert _edges(cfg) == {"Match@2": ["Return@4"], "Return@4": []}
    assert _function_exits(cfg) == {"Match@2", "Return@4"}


@pytest.mark.parametrize(
    "pattern",
    ["_ if items", "other if items", "[*_]"],
    ids=["guarded-wildcard", "guarded-capture", "sequence"],
)
def test_match_with_only_refutable_cases_falls_through(pattern: str) -> None:
    cfg = _cfg(f"""
        match value:
            case 1:
                value = 1
            case {pattern}:
                value = 2
        return value
        """)
    assert _edges(cfg)["Match@2"] == ["Assign@4", "Assign@6", "Return@7"]


@pytest.mark.parametrize(
    "pattern",
    ["_", "other", "_ as other", "1 | _", "(2 | other) as alias"],
    ids=["wildcard", "capture", "as-wildcard", "or-wildcard", "as-or-capture"],
)
def test_match_with_an_irrefutable_case_has_no_fall_through_edge(
    pattern: str,
) -> None:
    cfg = _cfg(f"""
        match value:
            case 1:
                value = 1
            case {pattern}:
                value = 2
        return value
        """)
    assert _edges(cfg)["Match@2"] == ["Assign@4", "Assign@6"]
