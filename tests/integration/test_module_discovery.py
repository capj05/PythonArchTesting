"""
Integration tests for direct module discovery behavior.
"""

from pathlib import Path

from src.state import ProjectState


def test_discover_modules_returns_empty_without_target_path():
    state = ProjectState("/test", [])
    state.target_project_path = None

    assert state.discover_modules() == []


def test_discover_modules_finds_nested_modules_and_is_stable(tmp_path: Path):
    (tmp_path / "module1.py").write_text("# module 1\n", encoding="utf-8")
    pkg = tmp_path / "subdir"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# package\n", encoding="utf-8")
    (pkg / "module2.py").write_text("# module 2\n", encoding="utf-8")
    deep = tmp_path / "level1" / "level2" / "level3"
    deep.mkdir(parents=True)
    (deep / "deep_module.py").write_text("# deep module\n", encoding="utf-8")

    state = ProjectState(str(tmp_path), [])

    first = state.discover_modules()
    second = state.discover_modules()

    assert first == second
    assert first == [
        "level1.level2.level3.deep_module",
        "module1",
        "subdir.__init__",
        "subdir.module2",
    ]


def test_get_module_file_path_handles_modules_and_packages(tmp_path: Path):
    (tmp_path / "module1.py").write_text("# module 1\n", encoding="utf-8")
    pkg = tmp_path / "subdir"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# package\n", encoding="utf-8")

    state = ProjectState(str(tmp_path), [])

    assert state._get_module_file_path("module1", str(tmp_path)) == str(
        tmp_path / "module1.py"
    )
    assert state._get_module_file_path("subdir", str(tmp_path)) == str(
        tmp_path / "subdir" / "__init__.py"
    )
    assert state._get_module_file_path("missing", str(tmp_path)) is None
