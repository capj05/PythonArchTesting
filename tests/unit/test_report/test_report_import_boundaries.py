from __future__ import annotations

import ast
from pathlib import Path


def test_report_api_module_does_not_import_concrete_generators():
    path = Path("src/report/api.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))

    concrete_modules = {
        "src.report.json_generator",
        "src.report.markdown_generator",
    }
    concrete_relative = {
        "json_generator",
        "markdown_generator",
    }

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in concrete_modules:
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module in concrete_modules or (
                node.module in concrete_relative
            ):  # noqa: E501
                offenders.append(node.module or "")

    assert not offenders, f"api.py imports concrete generators: {offenders}"


def test_report_api_module_does_not_import_core():
    path = Path("src/report/api.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "src.report.core":
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "src.report.core" or module.endswith(".core"):
                offenders.append(module)

    assert not offenders, f"api.py imports report.core: {offenders}"


def test_report_modules_do_not_import_sqlalchemy():
    paths = [
        Path("src/report/api.py"),
        Path("src/report/dispatcher.py"),
        Path("src/report/json_generator.py"),
        Path("src/report/markdown_generator.py"),
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

    assert not offenders, (
        "Non-DB report modules import sqlalchemy: " f"{offenders}"
    )  # noqa: E501
