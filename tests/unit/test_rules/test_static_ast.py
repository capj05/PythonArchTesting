import ast
import textwrap

from pythonarchtesting.evidence.static_ast import collect_import_graph


def test_collect_import_graph_relative_and_asname():
    code = textwrap.dedent("""
        import os as myos
        from . import local as alias
        from ..pkg import mod as m
        """)
    tree = ast.parse(code)
    edges = collect_import_graph(tree)

    assert any(
        edge.kind == "import"
        and edge.module == "os"
        and edge.name is None
        and edge.asname == "myos"
        for edge in edges
    )
    assert any(
        edge.kind == "importfrom"
        and edge.module == "."
        and edge.name == "local"
        and edge.asname == "alias"
        for edge in edges
    )
    assert any(
        edge.kind == "importfrom"
        and edge.module == "..pkg"
        and edge.name == "mod"
        and edge.asname == "m"
        for edge in edges
    )

    sorted_edges = sorted(
        edges, key=lambda e: (e.module, e.name or "", e.lineno, e.asname or "")
    )
    assert edges == sorted_edges
