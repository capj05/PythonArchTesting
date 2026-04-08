"""
Import safety tests.

Tests that enforce architectural layer separation by ensuring certain modules
don't import forbidden dependencies.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

from tests.import_safety.rules import check_forbidden_imports


def capture_module_imports(target_module: str) -> List[str]:
    """
    Import a module in a fresh subprocess and capture all loaded modules.

    Args:
        target_module: The module to import (e.g., "pythonarchtesting.cli")

    Returns:
        List of module names that were loaded during import
    """
    # Python script to run in subprocess
    capture_script = f"""
import json
import sys

# Import the target module
import {target_module}

# Capture all loaded modules
loaded_modules = sorted(sys.modules.keys())

# Output as JSON for reliable parsing
print(json.dumps(loaded_modules))
"""

    # Run in a fresh subprocess to ensure isolation
    result = subprocess.run(
        [sys.executable, "-c", capture_script],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to import {target_module}: {result.stderr}")

    try:
        loaded_modules = json.loads(result.stdout)
        return loaded_modules
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Failed to parse module list from {target_module}: {e}"
        ) from e


@pytest.mark.parametrize(
    "target_module",
    [
        "pythonarchtesting.util.type_utils",
        "pythonarchtesting.report.dispatcher",
        "pythonarchtesting.cli",
    ],
)
def test_module_import_restrictions(target_module: str):
    """
    Test that importing target modules doesn't load forbidden dependencies.

    Args:
        target_module: The module to test
    """
    # Capture all modules loaded when importing the target
    loaded_modules = capture_module_imports(target_module)

    # Check for violations
    violations = check_forbidden_imports(loaded_modules, target_module)

    # Assert no violations found
    assert (
        not violations
    ), f"Importing {target_module} loaded forbidden modules: {violations}"


def test_util_type_utils_declaration_free_import():
    """
    Runtime import trace regression test for pythonarchtesting.util.type_utils.

    Ensures that importing pythonarchtesting.util.type_utils does not pull in
    pythonarchtesting.rules modules. This is a critical test for maintaining
    proper layering where util modules must remain independent of declaration
    code.
    """
    # Import type_utils in a fresh subprocess and capture loaded modules
    loaded_modules = capture_module_imports("pythonarchtesting.util.type_utils")

    declaration_modules = [
        module
        for module in loaded_modules
        if module.startswith("pythonarchtesting.rules")
    ]

    assert not declaration_modules, (
        "Importing pythonarchtesting.util.type_utils loaded "
        f"declaration modules: {declaration_modules}"
    )


@pytest.mark.parametrize(
    "target_module",
    [
        "pythonarchtesting.validation_scope",
        "pythonarchtesting.report.lazy",
        "pythonarchtesting.state.project_state._core",
    ],
)
def test_min_supported_python_module_import_smoke(target_module: str) -> None:
    """Import smoke test for modules that require the minimum supported syntax."""
    loaded_modules = capture_module_imports(target_module)

    assert loaded_modules, f"Importing {target_module} loaded no modules"
    assert target_module in loaded_modules


def test_harness_self_check(tmp_path: Path):
    """
    Self-check that validates the test harness can detect violations.

    Creates a temporary module that intentionally imports a forbidden module
    and verifies the detector correctly flags it.
    """
    # Create a temporary package structure
    temp_pkg = tmp_path / "temp_test_pkg"
    temp_pkg.mkdir()

    # Create __init__.py that imports a forbidden module
    init_file = temp_pkg / "__init__.py"
    init_file.write_text("""
# This module intentionally imports something that should be forbidden
# for testing the detection mechanism
import pythonarchtesting.execution
""".strip() + "\n")

    # Create a test script that imports our temp module
    test_script = f"""
import json
import sys

# Add temp directory to path so we can import our test module
sys.path.insert(0, r"{tmp_path}")

# Import the test module
import temp_test_pkg

# Capture loaded modules
loaded_modules = sorted(sys.modules.keys())
print(json.dumps(loaded_modules))
"""

    # Run the test
    result = subprocess.run(
        [sys.executable, "-c", test_script],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0, f"Test harness failed: {result.stderr}"

    # Parse loaded modules
    try:
        loaded_modules = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse test output: {e}") from e

    # Check that our detector finds the violation
    # We'll test against pythonarchtesting.util.type_utils rules since we imported
    # pythonarchtesting.execution
    violations = check_forbidden_imports(
        loaded_modules, "pythonarchtesting.util.type_utils"
    )

    # Should find the forbidden import
    assert any(
        "pythonarchtesting.execution" in v for v in violations
    ), "Test harness failed to detect forbidden import"
