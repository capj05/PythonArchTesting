"""
Helper functions for testing Python Architecture Testing toolkit.

This module provides utility functions to assist with test setup,
data generation, and common test patterns.
"""

import ast
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_module_from_file(file_path: Path) -> Any:
    """
    Load a Python module from a file path.

    Args:
        file_path: Path to the Python file

    Returns:
        The loaded module object

    Raises:
        ImportError: If the module cannot be loaded
    """
    spec = importlib.util.spec_from_file_location("test_module", file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_imports_from_file(file_path: Path) -> List[str]:
    """
    Extract all import statements from a Python file.

    Args:
        file_path: Path to the Python file

    Returns:
        List of import strings
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"from {module} import {alias.name}")

    return imports


def extract_functions_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Extract all function definitions from a Python file.

    Args:
        file_path: Path to the Python file

    Returns:
        List of dictionaries containing function information
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)
    functions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_info = {
                "name": node.name,
                "line": node.lineno,
                "args": [arg.arg for arg in node.args.args],
                "returns": ast.unparse(node.returns) if node.returns else None,
                "docstring": ast.get_docstring(node),
            }
            functions.append(func_info)

    return functions


def extract_classes_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Extract all class definitions from a Python file.

    Args:
        file_path: Path to the Python file

    Returns:
        List of dictionaries containing class information
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_info = {
                "name": node.name,
                "line": node.lineno,
                "bases": [ast.unparse(base) for base in node.bases],
                "docstring": ast.get_docstring(node),
                "methods": [],
            }

            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    method_info = {
                        "name": item.name,
                        "line": item.lineno,
                        "args": [arg.arg for arg in item.args.args],
                        "returns": ast.unparse(item.returns) if item.returns else None,
                        "docstring": ast.get_docstring(item),
                    }
                    class_info["methods"].append(method_info)

            classes.append(class_info)

    return classes


def create_test_project_structure(
    base_dir: Path,
    modules: Optional[List[str]] = None,
    with_circular_import: bool = False,
) -> Dict[str, Path]:
    """
    Create a test project structure with Python modules.

    Args:
        base_dir: Base directory for the test project
        modules: List of module names to create
        with_circular_import: Whether to create circular imports

    Returns:
        Dictionary mapping module names to their file paths
    """
    if modules is None:
        modules = ["module_a", "module_b", "module_c"]

    base_dir.mkdir(parents=True, exist_ok=True)
    src_dir = base_dir / "src"
    src_dir.mkdir(exist_ok=True)

    # Create __init__.py
    (src_dir / "__init__.py").touch()

    module_files = {}

    for i, module in enumerate(modules):
        file_path = src_dir / f"{module}.py"

        # Create module content
        imports = []
        if i > 0:
            imports.append(
                f"from .module_{chr(97 + i - 1)} import function_{chr(97 + i - 1)}"
            )

        if with_circular_import and module == modules[-1]:
            imports.append("from .module_a import function_a")

        content = f'''
"""{module.title()} module for testing."""

{chr(10).join(imports)}

class {module.title().replace('_', '')}:
    """Test class in {module}."""

    def __init__(self):
        self.name = "{module}"

    def method_{module}(self):
        return "method_{module}_result"

def function_{module}():
    """Test function in {module}."""
    return "function_{module}_result"

def complex_function_{module}(data: list) -> dict:
    """Complex function for testing in {module}."""
    result = {{}}
    for item in data:
        if isinstance(item, str):
            result[item] = len(item)
        elif isinstance(item, (int, float)):
            result[f"num_{{item}}"] = item * 2
    return result
'''

        file_path.write_text(content.strip())
        module_files[module] = file_path

    return module_files


def calculate_cyclomatic_complexity(file_path: Path) -> int:
    """
    Calculate cyclomatic complexity of a Python file.

    Args:
        file_path: Path to the Python file

    Returns:
        Cyclomatic complexity score
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)
    complexity = 1  # Base complexity

    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
            complexity += 1
        elif isinstance(node, ast.ExceptHandler):
            complexity += 1
        elif isinstance(node, ast.With, ast.AsyncWith):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1
        elif isinstance(node, ast.ListComp):
            complexity += 1
        elif isinstance(node, ast.DictComp):
            complexity += 1
        elif isinstance(node, ast.SetComp):
            complexity += 1
        elif isinstance(node, ast.GeneratorExp):
            complexity += 1

    return complexity


def create_mock_config(
    rules: Optional[List[Dict[str, Any]]] = None, project_name: str = "test_project"
) -> Dict[str, Any]:
    """
    Create a mock configuration for testing.

    Args:
        rules: List of validation rules
        project_name: Name of the test project

    Returns:
        Configuration dictionary
    """
    if rules is None:
        rules = [
            {"name": "no_circular_imports", "type": "import_analysis", "enabled": True},
            {
                "name": "max_complexity",
                "type": "complexity_analysis",
                "enabled": True,
                "threshold": 10,
            },
        ]

    return {
        "project": {
            "name": project_name,
            "version": "1.0.0",
            "description": f"Test project {project_name} for architecture validation",
        },
        "validation": {"rules": rules},
        "reporting": {
            "format": "json",
            "output": f"{project_name}_validation_report.json",
        },
    }


def assert_file_contains(
    file_path: Path, content: str, should_contain: bool = True
) -> bool:
    """
    Assert that a file contains (or doesn't contain) specific content.

    Args:
        file_path: Path to the file
        content: Content to search for
        should_contain: Whether the content should be present

    Returns:
        True if assertion passes

    Raises:
        AssertionError: If assertion fails
    """
    file_content = file_path.read_text(encoding="utf-8")

    if should_contain:
        assert content in file_content, f"File {file_path} does not contain: {content}"
    else:
        assert content not in file_content, f"File {file_path} contains: {content}"

    return True


def get_test_file_path(test_name: str) -> Path:
    """
    Get a standardized test file path.

    Args:
        test_name: Name of the test

    Returns:
        Path for the test file
    """
    return (
        Path(__file__).parent.parent / "fixtures" / "test_configs" / f"{test_name}.json"
    )


def cleanup_test_files(*file_paths: Path) -> None:
    """
    Clean up test files after testing.

    Args:
        *file_paths: Variable number of file paths to clean up
    """
    for file_path in file_paths:
        try:
            if file_path.exists():
                if file_path.is_file():
                    file_path.unlink()
                elif file_path.is_dir():
                    import shutil

                    shutil.rmtree(file_path)
        except OSError:
            # Ignore cleanup errors
            pass
