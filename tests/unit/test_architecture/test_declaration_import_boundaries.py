from __future__ import annotations

import ast
from pathlib import Path


def _imports_for_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_declaration_layer_does_not_import_execution_runtime_or_reporting():
    declaration_root = Path("src/pythonarchtesting/rules/declaration")
    forbidden_prefixes = (
        "pythonarchtesting.execution",
        "pythonarchtesting.report",
        "pythonarchtesting.state",
        "pythonarchtesting.matching",
        "pythonarchtesting.discovery",
    )

    offenders: list[str] = []
    for file_path in declaration_root.rglob("*.py"):
        imports = _imports_for_file(file_path)
        for module_name in imports:
            if module_name.startswith(forbidden_prefixes):
                offenders.append(f"{file_path}:{module_name}")

    assert not offenders, f"Declaration layer imports forbidden modules: {offenders}"
