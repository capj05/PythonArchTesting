from __future__ import annotations

import ast
from pathlib import Path


def test_report_modules_do_not_import_sqlalchemy():
    paths = [
        Path("src/pythonarchtesting/report/api.py"),
        Path("src/pythonarchtesting/report/renderers/json.py"),
        Path("src/pythonarchtesting/report/renderers/markdown_bundle.py"),
    ]
    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("sqlalchemy"):
                        offenders.append(f"{path}:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").startswith("sqlalchemy"):
                    offenders.append(f"{path}:{node.module}")

    assert not offenders, "Non-DB report modules import sqlalchemy: " f"{offenders}"
