"""
Tests for source module resolution handling.
"""

from pathlib import Path

from src.config.data import create_config_from_dict
from src.state import ProjectState
from src.state.source_resolution import resolve_source_module_files


def test_resolve_source_module_files_finds_stub_module_from_source_root(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "reference"
    source_root.mkdir()
    module_path = source_root / "rules.pyi"
    module_path.write_text("VALUE: int\n", encoding="utf-8")

    files, errors = resolve_source_module_files(
        "rules", source_root, prefer_stub_files=True
    )

    assert files == [module_path]
    assert errors == []


def test_resolve_source_module_files_finds_stub_package_from_source_root(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "reference"
    package_dir = source_root / "pkg"
    package_dir.mkdir(parents=True)
    package_init = package_dir / "__init__.pyi"
    package_init.write_text("VALUE: int\n", encoding="utf-8")

    files, errors = resolve_source_module_files(
        "pkg", source_root, prefer_stub_files=True
    )

    assert files == [package_init]
    assert errors == []


def test_resolve_source_module_files_keeps_python_modules_working(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "reference"
    source_root.mkdir()
    module_path = source_root / "rules.py"
    module_path.write_text("VALUE = 1\n", encoding="utf-8")

    files, errors = resolve_source_module_files("rules", source_root)

    assert files == [module_path]
    assert errors == []


def test_resolve_source_module_files_in_stub_mode_rejects_python_only_module(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "reference"
    source_root.mkdir()
    module_path = source_root / "rules.py"
    module_path.write_text("VALUE = 1\n", encoding="utf-8")

    files, errors = resolve_source_module_files(
        "rules", source_root, prefer_stub_files=True
    )

    assert files == []
    assert len(errors) == 1
    assert errors[0].check_type == "extraction/source_resolution"


def test_source_module_resolution_failure(tmp_path: Path) -> None:
    config = create_config_from_dict(
        {"projects": {"source_path": str(tmp_path / "reference")}}
    )
    state = ProjectState(str(tmp_path), [], config=config)
    state.initialize(str(tmp_path))
    state.reference_modules = ["nonexistent.module"]

    state.build_entity_indexes()

    assert not state.source_entities
    assert any(
        result.check_type == "extraction/source_resolution"
        for result in state.validation_results
    )
