"""
Comprehensive pytest configuration for Python Architecture Testing.

This module provides shared fixtures, configuration, and utilities
for all test types across the project.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List
from unittest.mock import Mock

import pytest
from _pytest.config import Config

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# Add tests to Python path for test utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    from src.state import ProjectState, ValidationStatus
except ImportError:
    # These imports may fail if the modules don't exist yet
    ProjectState = None
    ValidationStatus = None


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Return the path to the test data directory."""
    return Path(__file__).parent / "sample_projects"


@pytest.fixture(scope="session")
def test_configs_dir() -> Path:
    """Return the path to the test configurations directory."""
    return Path(__file__).parent / "test_configs"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_project_dir(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary project directory with basic structure."""
    project_dir = temp_dir / "test_project"
    project_dir.mkdir()

    # Create basic Python project structure
    (project_dir / "src").mkdir()
    (project_dir / "tests").mkdir()
    (project_dir / "docs").mkdir()

    # Create __init__.py files
    (project_dir / "src" / "__init__.py").touch()
    (project_dir / "tests" / "__init__.py").touch()

    yield project_dir


@pytest.fixture(autouse=True)
def reset_project_state() -> Generator[None, None, None]:
    """Provide test-level hook for ProjectState cleanup."""
    yield


@pytest.fixture
def clean_project_state() -> Any:
    """Provide a clean ProjectState instance for testing."""
    if not ProjectState:
        pytest.skip("ProjectState not available")

    state = ProjectState("/test", [])
    if hasattr(state, "reference_modules"):
        state.reference_modules = []
    if hasattr(state, "imported_modules"):
        state.imported_modules = {}
    if hasattr(state, "target_functions"):
        state.target_functions = {}
    if hasattr(state, "validation_results"):
        state.validation_results = []
    if hasattr(state, "validation_stats"):
        state.validation_stats = {}
    return state


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Provide a sample configuration for testing."""
    return {
        "discovery": {
            "exclude_hidden_dirs": True,
            "excluded_dirs": [".git", "__pycache__"],
            "included_file_patterns": ["*.py"],
        },
        "report": {"schema_version": "2", "warnings_as_fail": False},
        "projects": {"source_path": ".", "target_path": "./target"},
    }


@pytest.fixture
def mock_config_manager(sample_config: Dict[str, Any]) -> Mock:
    """Provide a mock config object for testing."""
    manager = Mock()
    manager.config = sample_config
    manager.get.return_value = sample_config
    manager.load.return_value = sample_config
    manager.save.return_value = True
    return manager


@pytest.fixture
def sample_python_file(temp_project_dir: Path) -> Path:
    """Create a sample Python file for testing."""
    file_path = temp_project_dir / "src" / "sample_module.py"

    content = '''
"""Sample module for testing architecture validation."""

from typing import List, Dict, Optional, Any

class SampleClass:
    """A sample class for testing."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._data: List[str] = []

    def add_item(self, item: str) -> None:
        """Add an item to the data list."""
        self._data.append(item)

    def get_items(self) -> List[str]:
        """Get all items."""
        return self._data.copy()

    def process_data(self, data: Dict[str, Any]) -> Optional[str]:
        """Process data and return result."""
        if not data:
            return None

        result = f"Processed {len(data)} items"
        return result


def sample_function(x: int, y: str) -> str:
    """A sample function for testing."""
    return f"{x}: {y}"


def complex_function(data: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """A more complex function for testing complexity analysis."""
    result = {}

    for item in data:
        if 'key' in item and 'value' in item:
            key = item['key']
            value = item['value']

            if key not in result:
                result[key] = []

            if isinstance(value, list):
                for v in value:
                    if isinstance(v, str):
                        result[key].append(v.upper())
                    elif isinstance(v, dict):
                        nested_result = process_nested_dict(v)
                        result[key].extend(nested_result)
            else:
                result[key].append(str(value))

    return result


def process_nested_dict(nested: Dict[str, Any]) -> List[str]:
    """Process nested dictionary."""
    results = []

    for k, v in nested.items():
        if isinstance(v, str):
            results.append(v)
        elif isinstance(v, dict):
            results.extend(process_nested_dict(v))
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    results.append(item)

    return results
'''

    file_path.write_text(content)
    return file_path


@pytest.fixture
def sample_python_files(temp_project_dir: Path) -> List[Path]:
    """Create multiple sample Python files for testing."""
    files = []

    # Main module
    main_file = temp_project_dir / "src" / "main.py"
    main_content = '''
"""Main module for the test project."""

from .module_a import ClassA
from .module_b import function_b
from .utils import helper_function

class MainClass:
    """Main class that uses other modules."""

    def __init__(self):
        self.class_a = ClassA()

    def process(self, data):
        result = function_b(data)
        return helper_function(result)
'''
    main_file.write_text(main_content)
    files.append(main_file)

    # Module A
    module_a = temp_project_dir / "src" / "module_a.py"
    module_a_content = '''
"""Module A with ClassA."""

class ClassA:
    """Class A for testing."""

    def method_a(self):
        return "A"
'''
    module_a.write_text(module_a_content)
    files.append(module_a)

    # Module B
    module_b = temp_project_dir / "src" / "module_b.py"
    module_b_content = '''
"""Module B with function_b."""

def function_b(data):
    """Function B for testing."""
    return processed_data

def processed_data():
    return "processed"
'''
    module_b.write_text(module_b_content)
    files.append(module_b)

    # Utils module
    utils = temp_project_dir / "src" / "utils.py"
    utils_content = '''
"""Utility functions."""

def helper_function(data):
    """Helper function."""
    return f"helped: {data}"
'''
    utils.write_text(utils_content)
    files.append(utils)

    return files


@pytest.fixture
def circular_import_files(temp_project_dir: Path) -> List[Path]:
    """Create files with circular imports for testing."""
    # Module X
    module_x = temp_project_dir / "src" / "module_x.py"
    module_x_content = '''
"""Module X with circular import to module_y."""

from .module_y import function_y

def function_x():
    return function_y()
'''
    module_x.write_text(module_x_content)

    # Module Y
    module_y = temp_project_dir / "src" / "module_y.py"
    module_y_content = '''
"""Module Y with circular import to module_x."""

from .module_x import function_x

def function_y():
    return function_x()
'''
    module_y.write_text(module_y_content)

    return [module_x, module_y]


@pytest.fixture
def performance_test_data() -> Dict[str, Any]:
    """Provide data for performance testing."""
    return {
        "small_dataset": list(range(100)),
        "medium_dataset": list(range(1000)),
        "large_dataset": list(range(10000)),
        "complex_structure": {
            f"key_{i}": {"nested": list(range(10)), "data": f"value_{i}"}
            for i in range(100)
        },
    }


# Custom pytest markers
def pytest_configure(config: Config) -> None:
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "performance: mark test as a performance test")
    config.addinivalue_line("markers", "property: mark test as a property-based test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


# Test collection hooks
def pytest_collection_modifyitems(config: Config, items: List[Any]) -> None:
    """Modify test collection for better organization."""
    # Add markers based on file location
    for item in items:
        if "/unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "/performance/" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
        elif "/property/" in str(item.fspath):
            item.add_marker(pytest.mark.property)


# Legacy fixtures for backward compatibility
@pytest.fixture
def test_files_dir():
    """Return the path to the test files directory (legacy)."""
    return os.path.join(os.path.dirname(__file__), "..", "files")


@pytest.fixture
def create_test_file(test_files_dir):
    """
    Fixture that creates test files with specified content (legacy).

    Returns a function that can be called to create a test file.
    """
    # Ensure the test files directory exists
    os.makedirs(test_files_dir, exist_ok=True)

    created_files = []

    def _create_file(filename, content):
        filepath = os.path.join(test_files_dir, filename)
        with open(filepath, "w") as f:
            f.write(content)
        created_files.append(filepath)
        return filepath

    yield _create_file

    # Cleanup: delete any files created during the test
    for filepath in created_files:
        if os.path.exists(filepath):
            os.remove(filepath)
