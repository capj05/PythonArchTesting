from __future__ import annotations

import ast
from pathlib import Path


def test_report_package_does_not_import_sqlalchemy():
    report_root = Path("src/pythonarchtesting/report")
    offenders: list[str] = []

    for path in report_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("sqlalchemy"):
                        offenders.append(f"{path}:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").startswith("sqlalchemy"):
                    offenders.append(f"{path}:{node.module}")

    assert (
        not offenders
    ), f"Unexpected sqlalchemy imports in report package: {offenders}"
