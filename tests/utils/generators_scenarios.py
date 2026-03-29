"""
Scenario and dataset generators for tests.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from .generators_project import generate_random_string


def generate_validation_scenarios() -> List[Dict[str, Any]]:
    """
    Generate various validation scenarios for testing.
    """
    scenarios = [
        {
            "name": "simple_valid_project",
            "description": "A simple valid project with no violations",
            "config": {
                "project": {"name": "simple_project"},
                "validation": {
                    "rules": [
                        {
                            "name": "no_circular_imports",
                            "type": "import_analysis",
                            "enabled": True,
                        },
                        {
                            "name": "max_complexity",
                            "type": "complexity_analysis",
                            "enabled": True,
                            "threshold": 10,
                        },
                    ]
                },
            },
            "expected_violations": 0,
        },
        {
            "name": "circular_import_project",
            "description": "Project with circular imports",
            "config": {
                "project": {"name": "circular_project"},
                "validation": {
                    "rules": [
                        {
                            "name": "no_circular_imports",
                            "type": "import_analysis",
                            "enabled": True,
                        }
                    ]
                },
            },
            "expected_violations": 1,
        },
        {
            "name": "high_complexity_project",
            "description": "Project with high complexity functions",
            "config": {
                "project": {"name": "complex_project"},
                "validation": {
                    "rules": [
                        {
                            "name": "max_complexity",
                            "type": "complexity_analysis",
                            "enabled": True,
                            "threshold": 5,
                        }
                    ]
                },
            },
            "expected_violations": 2,
        },
        {
            "name": "mixed_violations_project",
            "description": "Project with multiple types of violations",
            "config": {
                "project": {"name": "mixed_project"},
                "validation": {
                    "rules": [
                        {
                            "name": "no_circular_imports",
                            "type": "import_analysis",
                            "enabled": True,
                        },
                        {
                            "name": "max_complexity",
                            "type": "complexity_analysis",
                            "enabled": True,
                            "threshold": 8,
                        },
                    ]
                },
            },
            "expected_violations": 3,
        },
    ]

    return scenarios


def generate_performance_test_data(
    small_size: int = 100, medium_size: int = 1000, large_size: int = 10000
) -> Dict[str, Any]:
    """
    Generate data for performance testing.
    """
    return {
        "small_dataset": list(range(small_size)),
        "medium_dataset": list(range(medium_size)),
        "large_dataset": list(range(large_size)),
        "complex_structure": {
            f"key_{i}": {
                "nested": list(range(10)),
                "data": f"value_{i}",
                "metadata": {
                    "created": f"2023-01-{i % 28 + 1:02d}",
                    "tags": [f"tag_{j}" for j in range(i % 5)],
                    "active": i % 2 == 0,
                },
            }
            for i in range(100)
        },
        "nested_lists": [
            [random.randint(1, 100) for _ in range(random.randint(5, 20))]
            for _ in range(50)
        ],
        "string_data": [
            generate_random_string(random.randint(5, 50)) for _ in range(200)
        ],
    }


def generate_edge_case_scenarios() -> List[Dict[str, Any]]:
    """
    Generate edge case scenarios for testing.
    """
    return [
        {
            "name": "empty_project",
            "description": "Project with no Python files",
            "structure": {"files": []},
            "expected_behavior": "no_validation_results",
        },
        {
            "name": "single_file_project",
            "description": "Project with only one Python file",
            "structure": {"files": ["main.py"]},
            "expected_behavior": "successful_validation",
        },
        {
            "name": "deeply_nested_structure",
            "description": "Project with deeply nested directories",
            "structure": {"depth": 10, "files_per_dir": 2},
            "expected_behavior": "successful_validation",
        },
        {
            "name": "unicode_names",
            "description": "Project with Unicode file and function names",
            "structure": {
                "files": ["módulo.py", "функция.py", "関数.py"],
                "use_unicode_identifiers": True,
            },
            "expected_behavior": "successful_validation",
        },
        {
            "name": "very_long_names",
            "description": "Project with very long file and function names",
            "structure": {"name_length": 100, "use_long_names": True},
            "expected_behavior": "successful_validation",
        },
    ]


__all__ = [
    "generate_validation_scenarios",
    "generate_performance_test_data",
    "generate_edge_case_scenarios",
]
