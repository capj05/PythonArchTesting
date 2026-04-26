from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.rules import __all__ as public_rule_markers
from pythonarchtesting.rules.compilation import compile_rules


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _snippet_paths() -> list[Path]:
    return sorted((_repo_root() / "docs" / "snippets" / "patterns").glob("*.py"))


def test_pattern_snippets_parse_and_compile() -> None:
    snippet_paths = _snippet_paths()
    assert snippet_paths

    for path in snippet_paths:
        source_text = path.read_text(encoding="utf-8")
        ast.parse(source_text, filename=str(path))

        source_entities = extract_entities_from_source(
            source_text=source_text,
            file_path=path,
            root_path=_repo_root(),
            target_module_name=None,
            role="source",
            include_nested_functions=False,
            root_label="source",
        )
        rules, evidence, compiler_results = compile_rules(source_entities, Mock())

        assert rules, f"No rules compiled from {path}"
        assert evidence == [], f"Unexpected compiler evidence for {path}: {evidence}"
        assert (
            compiler_results == []
        ), f"Unexpected compiler results for {path}: {compiler_results}"


def test_pattern_snippets_only_import_public_rule_markers() -> None:
    public_markers = set(public_rule_markers)

    for path in _snippet_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_markers: set[str] = set()

        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "pythonarchtesting.rules":
                continue
            imported_markers.update(
                alias.name for alias in node.names if alias.name != "*"
            )

        assert imported_markers, f"No public rule markers imported in {path}"
        assert imported_markers <= public_markers, (
            f"Non-public markers imported in {path}: "
            f"{sorted(imported_markers - public_markers)}"
        )
