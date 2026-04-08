"""
Fixtures specific to integration tests.
"""

import shutil
from pathlib import Path
from typing import Generator, List
from uuid import uuid4

import pytest

from pythonarchtesting.state import ProjectState


@pytest.fixture
def temp_project_dir() -> Generator[Path, None, None]:
    """Create a temporary project for integration testing."""
    temp_root = Path(__file__).resolve().parents[2] / ".tmp_pytest_integration"
    temp_root.mkdir(exist_ok=True)
    temp_dir = temp_root / f"project-{uuid4().hex}"
    temp_dir.mkdir(parents=True)

    # Create project structure
    (temp_dir / "src").mkdir()
    (temp_dir / "tests").mkdir()
    (temp_dir / "docs").mkdir()

    # Create basic files
    (temp_dir / "src" / "__init__.py").touch()
    (temp_dir / "pyproject.toml").write_text("""
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "test-project"
version = "0.1.0"
""")

    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_python_files(temp_project_dir: Path) -> List[Path]:
    """Create sample Python files for testing."""
    src_dir = temp_project_dir / "src"

    # Create sample modules
    files = []

    # Main module
    main_file = src_dir / "main.py"
    main_file.write_text('''
"""Main module."""
from .utils import helper_function

def main():
    return helper_function("test")
''')
    files.append(main_file)

    # Utils module
    utils_file = src_dir / "utils.py"
    utils_file.write_text('''
"""Utility functions."""
def helper_function(data):
    return f"processed: {data}"
''')
    files.append(utils_file)

    # Models module
    models_file = src_dir / "models.py"
    models_file.write_text('''
"""Data models."""
class DataModel:
    def __init__(self, data):
        self.data = data

    def process(self):
        return str(self.data)
''')
    files.append(models_file)

    return files


@pytest.fixture
def clean_project_state() -> ProjectState:
    """Provide a clean project state instance."""
    state = ProjectState("/test", [])
    state.reset()
    return state
