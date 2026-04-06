from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import List

from src.config import Config


def _get_config_bool(config: Config, section: str, key: str, default: bool) -> bool:
    """Get boolean configuration value from new Config dataclass."""
    try:
        # Map section names to config attributes
        section_map = {
            "discovery": config.discovery,
            "matching": config.matching,
            "performance": config.performance,
            "logging": config.logging,
            "reporting": config.reporting,
            "files": config.files,
            "import_config": config.import_config,
            "error_handling": config.error_handling,
            "projects": config.projects,
            "report": config.report,
        }

        if section not in section_map:
            return default

        section_config = section_map[section]
        if hasattr(section_config, key):
            value = getattr(section_config, key)
            if isinstance(value, bool):
                return value

        # Fallback to raw config if available
        if config.raw and section in config.raw and key in config.raw[section]:
            value = config.raw[section][key]
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "1", "on")
            return bool(value)

        return default
    except Exception:
        return default


def _get_config_int(config: Config, section: str, key: str, default: int) -> int:
    """Get integer configuration value from new Config dataclass."""
    try:
        # Map section names to config attributes
        section_map = {
            "discovery": config.discovery,
            "matching": config.matching,
            "performance": config.performance,
            "logging": config.logging,
            "reporting": config.reporting,
            "files": config.files,
            "import_config": config.import_config,
            "error_handling": config.error_handling,
            "projects": config.projects,
            "report": config.report,
        }

        if section not in section_map:
            return default

        section_config = section_map[section]
        if hasattr(section_config, key):
            value = getattr(section_config, key)
            if isinstance(value, int):
                return value

        # Fallback to raw config if available
        if config.raw and section in config.raw and key in config.raw[section]:
            value = config.raw[section][key]
            try:
                return int(value)
            except (ValueError, TypeError):
                return default

        return default
    except Exception:
        return default


def _get_config_list(
    config: Config, section: str, key: str, default: List[str]
) -> List[str]:
    """Get list configuration value from new Config dataclass."""
    try:
        # Map section names to config attributes
        section_map = {
            "discovery": config.discovery,
            "matching": config.matching,
            "performance": config.performance,
            "logging": config.logging,
            "reporting": config.reporting,
            "files": config.files,
            "import_config": config.import_config,
            "error_handling": config.error_handling,
            "projects": config.projects,
            "report": config.report,
        }

        if section not in section_map:
            return default

        section_config = section_map[section]
        if hasattr(section_config, key):
            value = getattr(section_config, key)
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                return value

        # Fallback to raw config if available
        if config.raw and section in config.raw and key in config.raw[section]:
            value = config.raw[section][key]
            if isinstance(value, list):
                return value
            elif isinstance(value, str):
                return [item.strip() for item in value.split(",") if item.strip()]

        return default
    except Exception:
        return default


def discover_python_files(root_path: Path, config: Config) -> List[Path]:
    excluded_dirs = set(_get_config_list(config, "discovery", "excluded_dirs", []))
    vendor_defaults = {"venv", ".venv", "site-packages", "dist-info", "build", "dist"}
    excluded_dirs.update(vendor_defaults)

    exclude_hidden = _get_config_bool(config, "discovery", "exclude_hidden_dirs", True)
    include_patterns = _get_config_list(
        config, "discovery", "included_file_patterns", ["*.py"]
    )
    include_init = _get_config_bool(config, "discovery", "include_init_files", True)
    max_depth = _get_config_int(config, "discovery", "max_discovery_depth", -1)
    follow_symlinks = _get_config_bool(config, "discovery", "follow_symlinks", False)

    files: List[Path] = []
    for current_root, dirs, filenames in os.walk(
        root_path, followlinks=follow_symlinks
    ):
        rel_root = Path(current_root).relative_to(root_path)
        depth = len(rel_root.parts)
        if max_depth is not None and max_depth >= 0 and depth > max_depth:
            dirs[:] = []
            continue

        filtered_dirs = []
        for d in sorted(dirs):
            if exclude_hidden and d.startswith("."):
                continue
            if d in excluded_dirs:
                continue
            filtered_dirs.append(d)
        dirs[:] = filtered_dirs

        for filename in sorted(filenames):
            if filename in {"__init__.py", "__init__.pyi"} and not include_init:
                continue
            if not any(
                fnmatch.fnmatch(filename, pattern) for pattern in include_patterns
            ):
                continue
            files.append(Path(current_root) / filename)

    return sorted(
        files,
        key=lambda p: p.resolve().relative_to(root_path.resolve()).as_posix(),
    )


__all__ = ["discover_python_files"]
