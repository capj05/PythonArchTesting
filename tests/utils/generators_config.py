"""
Configuration data generators for tests.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


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
    _ = rules
    _ = project_name
    return {
        "discovery": {
            "exclude_hidden_dirs": True,
            "excluded_dirs": [".git", "__pycache__"],
            "included_file_patterns": ["*.py"],
        },
        "projects": {"source_path": ".", "target_path": "./target"},
        "report": {"schema_version": "2"},
    }


__all__ = ["create_mock_config"]
