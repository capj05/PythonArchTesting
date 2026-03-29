"""
Compatibility shim for test generators.

The implementation is split into focused modules:
- tests.utils.generators_config
- tests.utils.generators_project
- tests.utils.generators_scenarios
"""

from .generators_config import create_mock_config
from .generators_project import (
    generate_python_class,
    generate_python_function,
    generate_python_module,
    generate_random_string,
    generate_test_project,
)
from .generators_scenarios import (
    generate_edge_case_scenarios,
    generate_performance_test_data,
    generate_validation_scenarios,
)

__all__ = [
    "create_mock_config",
    "generate_random_string",
    "generate_python_function",
    "generate_python_class",
    "generate_python_module",
    "generate_test_project",
    "generate_validation_scenarios",
    "generate_performance_test_data",
    "generate_edge_case_scenarios",
]
