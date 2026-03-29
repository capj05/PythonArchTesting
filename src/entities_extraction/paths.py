from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Optional


def _is_package_init(file_path: Path) -> bool:
    return file_path.name in {"__init__.py", "__init__.pyi"}


def module_path_from_file(
    file_path: Path,
    root_path: Path,
    target_module_name: Optional[str],
) -> tuple[str, str]:
    try:
        rel_path = file_path.resolve().relative_to(root_path.resolve())
    except Exception:
        rel_path = Path(file_path.name)

    filepath_rel = PurePosixPath(rel_path).as_posix()
    if _is_package_init(rel_path):
        module_core = ".".join(rel_path.parent.parts)
    else:
        module_core = ".".join(rel_path.with_suffix("").parts)

    module_path = module_core
    if target_module_name:
        if module_core == "":
            module_path = target_module_name
        else:
            module_path = f"{target_module_name}.{module_core}"

    return module_path, filepath_rel


def root_path_from_module_path(module_path: str, file_path: Path) -> Path:
    parts = module_path.split(".") if module_path else []
    ups = len(parts) if _is_package_init(file_path) else max(len(parts) - 1, 0)
    root = file_path.parent
    for _ in range(ups):
        root = root.parent
    return root


__all__ = ["module_path_from_file", "root_path_from_module_path"]
