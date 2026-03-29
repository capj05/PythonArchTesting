"""
Module discovery functionality for finding Python modules.
"""

import fnmatch
import os
import pathlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.accessors import get_bool, get_int, get_list
from src.constants import FileConstants
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ModuleDiscovery:
    """
    Handles discovery of Python modules in a project directory.

    This class provides functionality to discover Python modules in a
    directory tree with deterministic ordering.
    """

    def __init__(self, path: Optional[str] = None, config: Optional[Any] = None):
        """Initialize the module discovery component."""
        self.target_project_path: Optional[str] = path
        self._config: Optional[Any] = config
        self._discovery_config: Optional[Dict[str, Any]] = None

    def set_target_path(self, path: Optional[str]) -> None:
        """Set the target project path for module discovery."""
        self.target_project_path = path

    def set_config(self, config: Optional[Any]) -> None:
        """Set configuration object used for discovery accessors."""
        self._config = config
        self._discovery_config = None

    def get_discovery_config(self) -> Dict[str, Any]:
        """Get discovery configuration settings."""
        if self._discovery_config is None:
            include_patterns = get_list(
                self._config,
                "discovery",
                "included_file_patterns",
                get_list(
                    self._config,
                    "discovery",
                    "include_patterns",
                    ["*.py"],
                ),
            )
            if set(include_patterns) == {"*.pyi"}:
                include_patterns = ["*.py"]
            excluded_dirs = get_list(
                self._config,
                "discovery",
                "excluded_dirs",
                get_list(
                    self._config,
                    "discovery",
                    "exclude_dirs",
                    list(FileConstants.EXCLUDED_DIRS),
                ),
            )
            exclude_patterns = get_list(
                self._config, "discovery", "exclude_patterns", []
            )
            if exclude_patterns:
                excluded_dirs = list(dict.fromkeys(excluded_dirs + exclude_patterns))
            self._discovery_config = {
                "included_file_patterns": include_patterns,
                "excluded_dirs": excluded_dirs,
                "exclude_hidden_dirs": get_bool(
                    self._config, "discovery", "exclude_hidden_dirs", True
                ),
                "follow_symlinks": get_bool(
                    self._config, "discovery", "follow_symlinks", False
                ),
                "max_discovery_depth": get_int(
                    self._config, "discovery", "max_discovery_depth", -1
                ),
                "include_init_files": get_bool(
                    self._config, "discovery", "include_init_files", True
                ),
            }
        return self._discovery_config

    def process_directory(
        self,
        root: str,
        dirs: List[str],
        files: List[str],
        target_path: pathlib.Path,
        config: Dict[str, Any],
    ) -> List[str]:
        """Process a directory and return module paths found in it."""
        modules: List[str] = []

        exclude_hidden = config.get("exclude_hidden_dirs", True)
        excluded_dirs = list(config.get("excluded_dirs", []))
        dirs[:] = [
            d
            for d in sorted(dirs)
            if not any(fnmatch.fnmatch(d, pattern) for pattern in excluded_dirs)
            and (not exclude_hidden or not d.startswith("."))
        ]

        for file in sorted(files):
            if not any(
                fnmatch.fnmatch(file, pattern)
                for pattern in config.get("included_file_patterns", ["*.py"])
            ):
                continue

            if file in {"__init__.py", "__init__.pyi"} and not config.get(
                "include_init_files", True
            ):
                continue

            file_path = pathlib.Path(root) / file
            try:
                rel_path = file_path.relative_to(target_path)
            except ValueError:
                continue

            module_path = str(rel_path.with_suffix("")).replace(os.sep, ".")
            modules.append(module_path)

        return modules

    def get_module_file_path(
        self, module_path: str, target_path: pathlib.Path
    ) -> Optional[str]:
        """Get the file path for a given module path."""
        candidates = (
            target_path / (module_path.replace(".", os.sep) + ".py"),
            target_path / (module_path.replace(".", os.sep) + ".pyi"),
            target_path / module_path.replace(".", os.sep) / "__init__.py",
            target_path / module_path.replace(".", os.sep) / "__init__.pyi",
        )
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        return None

    def discover_modules(self) -> List[str]:
        """
        Discover modules for the configured project path.

        Returns:
            List of module paths (dot-separated)
        """
        if not self.target_project_path:
            return []

        modules: List[str] = []
        target_path = pathlib.Path(self.target_project_path)
        config = self.get_discovery_config()
        max_depth = config.get("max_discovery_depth", -1)
        follow_symlinks = bool(config.get("follow_symlinks", False))

        logger.debug("Running module discovery...")

        for root, dirs, files in os.walk(target_path, followlinks=follow_symlinks):
            rel_root = Path(root).relative_to(target_path)
            depth = len(rel_root.parts)
            if max_depth is not None and max_depth >= 0 and depth > max_depth:
                dirs[:] = []
                continue

            logger.debug(
                "Processing directory: %s, %s subdirectories, %s files",
                root,
                len(dirs),
                len(files),
            )
            modules.extend(
                self.process_directory(root, dirs, files, target_path, config)
            )

        return sorted(set(modules))
