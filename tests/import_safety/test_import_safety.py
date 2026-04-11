"""
Import safety tests.

Tests that enforce architectural layer separation by ensuring certain modules
don't import forbidden dependencies.
"""

from pathlib import Path

import pytest

from tests.import_safety.policies import check_forbidden_imports
from tests.utils.subprocess_imports import capture_module_imports, run_python_json


@pytest.mark.parametrize(
    "target_module",
    [
        "pythonarchtesting.util.type_utils",
        "pythonarchtesting.report.dispatcher",
        "pythonarchtesting.cli",
    ],
)
def test_module_import_restrictions(target_module: str) -> None:
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


def test_util_type_utils_declaration_free_import() -> None:
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
        "pythonarchtesting.state._project_state._core",
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
    loaded_payload = run_python_json(f"""
import importlib
import json
import sys

sys.path.insert(0, {str(tmp_path)!r})
importlib.import_module("temp_test_pkg")
print(json.dumps(sorted(sys.modules.keys())))
""")
    assert isinstance(loaded_payload, list)
    loaded_modules = [str(module) for module in loaded_payload]

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
