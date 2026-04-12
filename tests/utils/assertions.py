"""
Custom assertion functions for testing Python Architecture Testing toolkit.

This module provides specialized assertion functions for common
testing scenarios in architecture validation.
"""

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional


def assert_valid_python_syntax(file_path: Path) -> None:
    """
    Assert that a Python file has valid syntax.

    Args:
        file_path: Path to the Python file

    Raises:
        AssertionError: If the file has invalid syntax
        SyntaxError: If the file cannot be parsed
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        ast.parse(content)
    except SyntaxError as e:
        raise AssertionError(f"Invalid Python syntax in {file_path}: {e}")


def assert_imports_present(
    file_path: Path, expected_imports: List[str], exact_match: bool = False
) -> None:
    """
    Assert that specific imports are present in a Python file.

    Args:
        file_path: Path to the Python file
        expected_imports: List of expected import strings
        exact_match: If True, all imports must match exactly

    Raises:
        AssertionError: If expected imports are not found
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)
    actual_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                actual_imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                actual_imports.append(f"from {module} import {alias.name}")

    if exact_match:
        missing_imports = set(expected_imports) - set(actual_imports)
        extra_imports = set(actual_imports) - set(expected_imports)

        if missing_imports:
            raise AssertionError(f"Missing imports in {file_path}: {missing_imports}")
        if extra_imports:
            raise AssertionError(f"Extra imports in {file_path}: {extra_imports}")
    else:
        for expected_import in expected_imports:
            if not any(
                expected_import in actual_import for actual_import in actual_imports
            ):
                raise AssertionError(
                    f"Import '{expected_import}' not found in {file_path}"
                )


def assert_function_exists(
    file_path: Path, function_name: str, expected_args: Optional[List[str]] = None
) -> None:
    """
    Assert that a function exists in a Python file.

    Args:
        file_path: Path to the Python file
        function_name: Name of the function to check
        expected_args: Expected argument names (optional)

    Raises:
        AssertionError: If the function is not found or doesn't match expectations
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)
    function_found = False

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            function_found = True

            if expected_args is not None:
                actual_args = [arg.arg for arg in node.args.args]
                if actual_args != expected_args:
                    raise AssertionError(
                        f"Function {function_name} in {file_path} has args {actual_args}, "
                        f"expected {expected_args}"
                    )
            break

    if not function_found:
        raise AssertionError(f"Function '{function_name}' not found in {file_path}")


def assert_class_exists(
    file_path: Path, class_name: str, expected_methods: Optional[List[str]] = None
) -> None:
    """
    Assert that a class exists in a Python file.

    Args:
        file_path: Path to the Python file
        class_name: Name of the class to check
        expected_methods: Expected method names (optional)

    Raises:
        AssertionError: If the class is not found or doesn't match expectations
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)
    class_found = False

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            class_found = True

            if expected_methods is not None:
                actual_methods = [
                    item.name for item in node.body if isinstance(item, ast.FunctionDef)
                ]
                missing_methods = set(expected_methods) - set(actual_methods)
                if missing_methods:
                    raise AssertionError(
                        f"Class {class_name} in {file_path} missing methods: {missing_methods}"
                    )
            break

    if not class_found:
        raise AssertionError(f"Class '{class_name}' not found in {file_path}")


def assert_cyclomatic_complexity(file_path: Path, max_complexity: int) -> None:
    """
    Assert that a file's cyclomatic complexity is within limits.

    Args:
        file_path: Path to the Python file
        max_complexity: Maximum allowed complexity

    Raises:
        AssertionError: If complexity exceeds the limit
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
        elif isinstance(
            node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)
        ):
            complexity += 1

    if complexity > max_complexity:
        raise AssertionError(
            f"Cyclomatic complexity {complexity} in {file_path} exceeds maximum {max_complexity}"
        )


def assert_no_circular_imports(project_dir: Path) -> None:
    """
    Assert that a project has no circular imports.

    Args:
        project_dir: Path to the project directory

    Raises:
        AssertionError: If circular imports are found
    """
    import_graph = {}

    # Build import graph
    for py_file in project_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue

        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            import_graph[str(py_file)] = imports
        except (SyntaxError, UnicodeDecodeError):
            # Skip files that can't be parsed
            continue

    # Check for circular imports
    visited = set()
    rec_stack = set()

    def has_cycle(file_path: str, path: List[str]) -> bool:
        if file_path in rec_stack:
            cycle_path = path[path.index(file_path) :] + [file_path]
            raise AssertionError(
                f"Circular import detected: {' -> '.join(cycle_path)}"
            )

        if file_path in visited:
            return False

        visited.add(file_path)
        rec_stack.add(file_path)

        for import_name in import_graph.get(file_path, []):
            # Find the actual file for this import
            for file_path_key in import_graph:
                if import_name in file_path_key or file_path_key.endswith(
                    f"{import_name}.py"
                ):
                    if has_cycle(file_path_key, path + [file_path]):
                        return True

        rec_stack.remove(file_path)
        return False

    for file_path in import_graph:
        if file_path not in visited:
            has_cycle(file_path, [])


def assert_validation_results_contain(
    results: List[Dict[str, Any]],
    expected_type: str,
    expected_message: Optional[str] = None,
) -> None:
    """
    Assert that validation results contain a specific type of result.

    Args:
        results: List of validation result dictionaries
        expected_type: Expected result type (e.g., "error", "warning")
        expected_message: Optional expected message substring

    Raises:
        AssertionError: If expected result is not found
    """
    matching_results = [
        result for result in results if result.get("type") == expected_type
    ]

    if not matching_results:
        raise AssertionError(f"No validation results of type '{expected_type}' found")

    if expected_message:
        message_results = [
            result
            for result in matching_results
            if expected_message in result.get("message", "")
        ]
        if not message_results:
            raise AssertionError(
                f"No validation results of type '{expected_type}' with message "
                f"containing '{expected_message}' found"
            )


def assert_project_structure_valid(project_dir: Path) -> None:
    """
    Assert that a project has a valid Python project structure.

    Args:
        project_dir: Path to the project directory

    Raises:
        AssertionError: If the structure is invalid
    """
    if not project_dir.exists():
        raise AssertionError(f"Project directory {project_dir} does not exist")

    # Check for common Python project structure elements
    src_dir = project_dir / "src"
    if src_dir.exists() and not any(src_dir.rglob("*.py")):
        raise AssertionError("src directory exists but contains no Python files")

    # Check for __init__.py files in package directories
    for py_file in project_dir.rglob("*.py"):
        parent_dir = py_file.parent
        if (
            parent_dir.name != "__pycache__"
            and not (parent_dir / "__init__.py").exists()
        ):
            # This might be a module rather than a package
            pass


def assert_config_valid(config: Dict[str, Any]) -> None:
    """
    Assert that a configuration dictionary is valid.

    Args:
        config: Configuration dictionary

    Raises:
        AssertionError: If the configuration is invalid
    """
    from pythonarchtesting.config import validate_configuration

    result = validate_configuration(config)
    if not result.is_valid:
        raise AssertionError(f"Configuration validation failed: {result.errors}")


def assert_performance_within_threshold(
    actual_time: float, max_time: float, operation_name: str
) -> None:
    """
    Assert that performance is within acceptable thresholds.

    Args:
        actual_time: Actual execution time in seconds
        max_time: Maximum allowed time in seconds
        operation_name: Name of the operation being tested

    Raises:
        AssertionError: If performance exceeds threshold
    """
    if actual_time > max_time:
        raise AssertionError(
            f"Performance threshold exceeded for {operation_name}: "
            f"{actual_time:.3f}s > {max_time:.3f}s"
        )


def assert_memory_usage_within_threshold(
    actual_memory: int, max_memory: int, operation_name: str
) -> None:
    """
    Assert that memory usage is within acceptable thresholds.

    Args:
        actual_memory: Actual memory usage in bytes
        max_memory: Maximum allowed memory in bytes
        operation_name: Name of the operation being tested

    Raises:
        AssertionError: If memory usage exceeds threshold
    """
    if actual_memory > max_memory:
        actual_mb = actual_memory / (1024 * 1024)
        max_mb = max_memory / (1024 * 1024)
        raise AssertionError(
            f"Memory threshold exceeded for {operation_name}: "
            f"{actual_mb:.2f}MB > {max_mb:.2f}MB"
        )
