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


def test_legacy_runtime_layer_has_been_removed():
    assert not Path("src/runtime").exists()


def test_rule4_reporting_entrypoint_does_not_import_runtime_layer():
    report_entry = Path("src/report/api.py")
    imports = _imports_for_file(report_entry)
    offenders = [name for name in imports if name.startswith("src.runtime")]
    assert (
        not offenders
    ), f"Rule 4 violation: report API imports runtime layer: {offenders}"
