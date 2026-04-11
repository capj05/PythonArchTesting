"""
Main pytest configuration file.
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Generator, List
from uuid import uuid4

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
PYTEST_TEMP_ROOT = Path.cwd() / ".tmp_pytest_builtin" / uuid4().hex
PYTEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SRC_ROOT))
os.environ["PYTHONPATH"] = (
    str(SRC_ROOT)
    if not os.environ.get("PYTHONPATH")
    else f"{SRC_ROOT}{os.pathsep}{os.environ['PYTHONPATH']}"
)


class RepoTmpPathFactory:
    """Minimal tmp_path_factory implementation backed by a repo-local directory."""

    def __init__(self, base_path: Path, retention_policy: str) -> None:
        self._base_path = base_path
        self._retention_policy = retention_policy
        self._counters: Dict[str, int] = {}

    def getbasetemp(self) -> Path:
        return self._base_path

    def mktemp(self, basename: str, numbered: bool = True) -> Path:
        safe_name = "".join(
            ch if ch.isalnum() or ch in "._-" else "_" for ch in basename
        )
        if numbered:
            index = self._counters.get(safe_name, 0)
            self._counters[safe_name] = index + 1
            path = self._base_path / f"{safe_name}{index}"
        else:
            path = self._base_path / safe_name

        path.mkdir(parents=True, exist_ok=False)
        return path


@pytest.fixture(scope="session")
def tmp_path_factory(request: pytest.FixtureRequest) -> RepoTmpPathFactory:
    """Provide pytest's builtin tmp_path fixture with a repo-local temp factory."""
    return RepoTmpPathFactory(
        base_path=PYTEST_TEMP_ROOT,
        retention_policy=request.config.getini("tmp_path_retention_policy"),
    )


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
def repo_tmp_path() -> Generator[Path, None, None]:
    """Create a writable repo-local temp directory for tests that need it."""
    temp_root = Path.cwd() / ".tmp_test_runtime"
    temp_root.mkdir(exist_ok=True)
    temp_path = temp_root / uuid4().hex
    temp_path.mkdir()
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_dir(repo_tmp_path: Path) -> Path:
    """Temporary compatibility alias for tests that still need repo-local storage."""
    return repo_tmp_path


@pytest.fixture
def temp_project_dir(repo_tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary project directory with basic structure."""
    project_dir = repo_tmp_path / "test_project"
    project_dir.mkdir()

    # Create basic Python project structure
    (project_dir / "src").mkdir()
    (project_dir / "tests").mkdir()
    (project_dir / "docs").mkdir()

    # Create __init__.py files
    (project_dir / "src" / "__init__.py").touch()
    (project_dir / "tests" / "__init__.py").touch()

    yield project_dir


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


def pytest_collection_modifyitems(
    config: pytest.Config, items: List[pytest.Item]
) -> None:
    """Apply markers based on path segments (Windows-safe)."""
    for item in items:
        parts = Path(str(item.fspath)).parts
        if "unit" in parts:
            item.add_marker(pytest.mark.unit)
            continue
        if "integration" in parts:
            item.add_marker(pytest.mark.integration)
            continue
        if "performance" in parts:
            item.add_marker(pytest.mark.performance)
            continue
        if "property" in parts:
            item.add_marker(pytest.mark.property)
            continue
        if "tests" in parts:
            item.add_marker(pytest.mark.unit)
