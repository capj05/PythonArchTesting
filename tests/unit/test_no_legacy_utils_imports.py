"""Test to ensure no legacy src.utils imports exist."""

import ast
from pathlib import Path


def test_no_src_utils_imports():
    """Verify no src.utils imports exist in the codebase."""
    src_root = Path(__file__).parent.parent.parent.parent / "src"
    test_root = Path(__file__).parent.parent.parent.parent / "tests"

    # Files to check
    files_to_check = []
    for root in [src_root, test_root]:
        for py_file in root.rglob("*.py"):
            if "build" not in str(py_file) and "__pycache__" not in str(py_file):
                files_to_check.append(py_file)

    # Check each file for src.utils imports
    for file_path in files_to_check:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content)

            # Check for imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("src.utils"):
                            raise AssertionError(f"Found legacy import in {file_path}: {
                                    alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("src.utils"):
                        raise AssertionError(
                            f"Found legacy import in {file_path}: from {
                                node.module}"
                        )
        except SyntaxError:
            # Skip files with syntax errors
            continue


def test_src_utils_directory_deleted():
    """Verify src/utils directory no longer exists."""
    src_root = Path(__file__).parent.parent.parent.parent / "src"
    utils_dir = src_root / "utils"

    assert not utils_dir.exists(), f"Legacy directory {utils_dir} still exists"
