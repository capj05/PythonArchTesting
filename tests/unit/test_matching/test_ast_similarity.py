"""
Tests for AST fingerprint similarity.
"""

import textwrap
from pathlib import Path

from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import ast_similarity


def _entity_from_source(source: str, name: str) -> object:
    root = Path.cwd()
    path = root / f"{name}.py"
    entities = extract_entities_from_source(
        source,
        path,
        root,
        None,
        role="target",
        include_nested_functions=False,
    )
    return next(entity for entity in entities if entity.kind == "function")


def test_ast_similarity_variable_names() -> None:
    e1 = _entity_from_source(
        textwrap.dedent("""
            def f(x):
                y = x + 1
                return y
            """).strip() + "\n",
        "a",
    )
    e2 = _entity_from_source(
        textwrap.dedent("""
            def g(z):
                w = z + 1
                return w
            """).strip() + "\n",
        "b",
    )
    assert ast_similarity(e1, e2) >= 0.95


def test_ast_similarity_loop_vs_comprehension() -> None:
    e1 = _entity_from_source(
        textwrap.dedent("""
            def f(items):
                result = []
                for item in items:
                    result.append(item)
                return result
            """).strip() + "\n",
        "c",
    )
    e2 = _entity_from_source(
        textwrap.dedent("""
            def g(items):
                return [item for item in items]
            """).strip() + "\n",
        "d",
    )
    assert ast_similarity(e1, e2) < 0.9
