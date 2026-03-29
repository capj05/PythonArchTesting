"""
Tests for the global state management functionality.

This module contains tests for the ProjectState class.
"""

import importlib
import inspect
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

# Import the modules to be tested
from src.constants import ValidationConstants
from src.state import ProjectState


@pytest.fixture
def test_files_dir():
    """Return the path to the tests/files directory."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, "files")


@pytest.fixture(autouse=True)
def reset_project_state():
    """Create a fresh ProjectState baseline before each test."""
    # Reset reference modules
    project_state = ProjectState("/test", [])
    project_state.reference_modules = []
    return project_state


class TestProjectState:
    """Test cases for the ProjectState class."""

    def test_instances_are_isolated(self):
        """Test that ProjectState instances are distinct objects."""
        state1 = ProjectState("/test", [])
        state2 = ProjectState("/test", [])
        assert state1 is not state2

    def test_initialize(self, test_files_dir):
        """Test initialization of the ProjectState."""
        # Setup
        project_state = ProjectState(test_files_dir, [])

        # Execute
        result = project_state.initialize(test_files_dir)

        # Assert
        assert project_state.target_project_path == str(Path(test_files_dir).absolute())
        assert project_state.target_module_name is None
        assert result is project_state  # Should return self for chaining

    def test_import_module(self, monkeypatch, test_files_dir):
        """Test importing a module."""
        # Setup
        project_state = ProjectState(test_files_dir, [])
        project_state.initialize(test_files_dir)

        # Create a mock module
        mock_module = type("MockModule", (), {})()

        # Mock importlib.import_module
        def mock_import(name):
            assert name == "test.module"
            return mock_module

        monkeypatch.setattr(importlib, "import_module", mock_import)

        # Mock inspect.isfunction to return True for our test
        def mock_isfunction(_):
            return True

        monkeypatch.setattr(inspect, "isfunction", mock_isfunction)

        # Execute
        result = project_state.import_module("test.module")

        # Assert
        assert result is mock_module
        assert "test.module" in project_state.imported_modules

    def test_get_function(self, test_files_dir):
        """Test retrieving functions from the state."""
        # Setup
        project_state = ProjectState(test_files_dir, [])
        project_state.initialize(test_files_dir)

        # Add a test function to the state
        def test_function():
            return "test"

        project_state.target_functions["test.module"] = [test_function]
        project_state.import_order = ["test.module"]

        # Test retrieval
        result = project_state.get_function("test_function")
        assert result is test_function

        # Test retrieval of non-existent function
        result = project_state.get_function("nonexistent_function")
        assert result is None

    def test_find_reference_function(self, test_files_dir):
        """Test finding reference functions."""
        # Setup
        project_state = ProjectState(test_files_dir, [])
        project_state.initialize(test_files_dir)

        # Define a test function
        def target_function():
            return "target"

        # Add a reference module with the same function name
        class MockModule:
            pass

        mock_module = MockModule()

        def reference_function():
            return "reference"

        reference_function.__name__ = "target_function"

        setattr(mock_module, "target_function", reference_function)

        # Add module to imported modules
        project_state.imported_modules["mock_module"] = mock_module

        # Test finding the reference function
        result = project_state.find_reference_function(target_function)
        assert result is reference_function
        assert "mock_module" in project_state.target_functions

    def test_register_reference_modules_imports_in_sorted_order(
        self, monkeypatch, test_files_dir
    ):
        project_state = ProjectState(test_files_dir, [])
        project_state.initialize(test_files_dir)

        imported = []

        def mock_import(module_path):
            imported.append(module_path)
            return SimpleNamespace()

        monkeypatch.setattr(project_state, "import_module", mock_import)

        project_state.register_reference_modules("b.module", "a.module", "b.module")

        assert project_state.reference_modules == ["a.module", "b.module"]
        assert imported == ["a.module", "b.module"]

    def test_validate_functions_aggregates_results_and_errors(self, test_files_dir):
        project_state = ProjectState(test_files_dir, [])
        project_state.initialize(test_files_dir)

        def ok_func():
            return None

        def bad_func():
            return None

        project_state.target_functions = {"sample.module": [ok_func, bad_func]}

        def validate_func(func, module_path):
            if func.__name__ == "bad_func":
                raise ValueError(f"bad validation for {module_path}")
            return SimpleNamespace(status=ValidationConstants.ValidationStatus.OK)

        result = project_state.validate_functions(validate_func)

        assert result["success_count"] == 1
        assert result["failed_count"] == 1
        assert "sample.module.ok_func" in result["results"]
        assert "sample.module.bad_func" in result["errors"]
        assert "parallel_used" not in result
