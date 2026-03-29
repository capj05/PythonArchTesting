from pathlib import Path

from src.config.data import create_config_from_dict
from src.entities_extraction.paths import (
    module_path_from_file,
    root_path_from_module_path,
)
from src.util.discovery_utils import discover_python_files


def test_module_path_from_file_maps_stub_package_init_to_package(
    tmp_path: Path,
) -> None:
    root = tmp_path / "reference"
    package_init = root / "pkg" / "__init__.pyi"
    package_init.parent.mkdir(parents=True)
    package_init.write_text("VALUE: int\n", encoding="utf-8")

    module_path, filepath_rel = module_path_from_file(package_init, root, None)

    assert module_path == "pkg"
    assert filepath_rel == "pkg/__init__.pyi"


def test_root_path_from_module_path_handles_stub_package_init(tmp_path: Path) -> None:
    file_path = tmp_path / "reference" / "pkg" / "__init__.pyi"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("VALUE: int\n", encoding="utf-8")

    root = root_path_from_module_path("pkg", file_path)

    assert root == tmp_path / "reference"


def test_discovery_skips_stub_init_files_when_include_init_is_disabled(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "reference"
    package_dir = source_root / "pkg"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__init__.pyi").write_text("", encoding="utf-8")
    (package_dir / "rules.pyi").write_text("VALUE: int\n", encoding="utf-8")
    config = create_config_from_dict(
        {
            "discovery": {
                "included_file_patterns": ["*.py", "*.pyi"],
                "include_init_files": False,
            }
        }
    )

    files = discover_python_files(source_root, config)

    assert files == [package_dir / "rules.pyi"]
