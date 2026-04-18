"""
Integration tests for direct module discovery behavior.
"""

from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.entities_extraction.paths import module_path_from_file
from pythonarchtesting.util.discovery_utils import discover_python_files


def test_discover_python_files_returns_empty_for_empty_directory(tmp_path: Path):
    config = create_config_from_dict({})
    files = discover_python_files(tmp_path, config)
    assert files == []


def test_discover_python_files_finds_nested_files_and_is_stable(tmp_path: Path):
    (tmp_path / "module1.py").write_text("# module 1\n", encoding="utf-8")
    pkg = tmp_path / "subdir"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# package\n", encoding="utf-8")
    (pkg / "module2.py").write_text("# module 2\n", encoding="utf-8")
    deep = tmp_path / "level1" / "level2" / "level3"
    deep.mkdir(parents=True)
    (deep / "deep_module.py").write_text("# deep module\n", encoding="utf-8")

    config = create_config_from_dict({})

    first = discover_python_files(tmp_path, config)
    second = discover_python_files(tmp_path, config)

    assert first == second

    # Convert to module paths
    module_paths = []
    for f in first:
        mp, _ = module_path_from_file(f, tmp_path, None)
        module_paths.append(mp)

    assert module_paths == sorted(module_paths)
    assert "module1" in module_paths
    assert "subdir" in module_paths
    assert "subdir.module2" in module_paths
    assert "level1.level2.level3.deep_module" in module_paths


def test_module_path_from_file_handles_modules_and_packages(tmp_path: Path):
    (tmp_path / "module1.py").write_text("# module 1\n", encoding="utf-8")
    pkg = tmp_path / "subdir"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# package\n", encoding="utf-8")

    mp1, _ = module_path_from_file(tmp_path / "module1.py", tmp_path, None)
    mp2, _ = module_path_from_file(tmp_path / "subdir" / "__init__.py", tmp_path, None)

    assert mp1 == "module1"
    assert mp2 == "subdir"

    # Non-existent file should return empty or None-ish path
    result, _ = module_path_from_file(tmp_path / "missing.py", tmp_path, None)
    assert result == "missing"
