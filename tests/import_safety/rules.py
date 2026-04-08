"""
Import safety rules configuration.

Centralized definition of forbidden import patterns for different modules.
"""

from typing import Dict, List

# Forbidden import patterns for each target module
FORBIDDEN_IMPORTS: Dict[str, List[str]] = {
    "pythonarchtesting.util.type_utils": [
        "pythonarchtesting.execution",
        "pythonarchtesting.report",
        # Util modules should not pull in declaration or execution layers.
        "pythonarchtesting.rules",
    ],
    "pythonarchtesting.report.dispatcher": [
        "pythonarchtesting.report.formats",
        "pythonarchtesting.report.generators",
    ],
    "pythonarchtesting.cli": [
        "pythonarchtesting.execution",
        "pythonarchtesting.runner_multi",
        "pythonarchtesting.state._project_state",
        "pythonarchtesting.state.project_state",
    ],
}


def get_forbidden_imports(target_module: str) -> List[str]:
    """
    Get the list of forbidden import patterns for a target module.

    Args:
        target_module: The module to check imports for

    Returns:
        List of forbidden import patterns (prefixes)
    """
    return FORBIDDEN_IMPORTS.get(target_module, [])


def check_forbidden_imports(loaded_modules: List[str], target_module: str) -> List[str]:
    """
    Check if any loaded modules match forbidden patterns for the target.

    Args:
        loaded_modules: List of module names that were loaded
        target_module: The module that was imported

    Returns:
        List of forbidden modules that were found
    """
    forbidden_patterns = get_forbidden_imports(target_module)
    violations = []

    for module in loaded_modules:
        for pattern in forbidden_patterns:
            if module.startswith(pattern):
                violations.append(module)

    return violations
