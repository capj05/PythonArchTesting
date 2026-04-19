from __future__ import annotations

import ast
from pathlib import Path


def test_report_api_module_does_not_import_compatibility_layers():
    path = Path("src/pythonarchtesting/report/api.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))

    compatibility_modules = {
        "pythonarchtesting.report.core",
        "pythonarchtesting.report.dispatcher",
        "pythonarchtesting.report.base_generator",
        "pythonarchtesting.report.json_generator",
        "pythonarchtesting.report.markdown_generator",
    }
    compatibility_relative = {
        "core",
        "dispatcher",
        "base_generator",
        "json_generator",
        "markdown_generator",
    }

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in compatibility_modules:
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in compatibility_modules or module in compatibility_relative:
                offenders.append(module)

    assert not offenders, f"api.py imports compatibility layers: {offenders}"


def test_report_modules_do_not_import_sqlalchemy():
    paths = [
        Path("src/pythonarchtesting/report/api.py"),
        Path("src/pythonarchtesting/report/dispatcher.py"),
        Path("src/pythonarchtesting/report/json_generator.py"),
        Path("src/pythonarchtesting/report/markdown_generator.py"),
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
