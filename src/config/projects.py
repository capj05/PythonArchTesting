"""
Multi-target project configuration resolution.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from src.exceptions import ConfigurationError, ErrorContext

from .data import Config


@dataclass(frozen=True)
class TargetSpec:
    target_id: str
    path: Path


@dataclass(frozen=True)
class ProjectsConfig:
    source_path: Path
    targets: List[TargetSpec]


def _normalize_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _resolve_target_ids(paths: Iterable[Path]) -> List[TargetSpec]:
    ordered = [p.resolve() for p in paths]
    sorted_paths = sorted(ordered, key=lambda p: str(p))
    counts: dict[str, int] = {}
    id_map: dict[Path, str] = {}

    for path in sorted_paths:
        base = path.name
        counts[base] = counts.get(base, 0) + 1
        suffix = counts[base]
        target_id = base if suffix == 1 else f"{base}-{suffix}"
        id_map[path] = target_id

    return [TargetSpec(target_id=id_map[path], path=path) for path in ordered]


def _has_python_files(path: Path) -> bool:
    if not path.is_dir():
        return False
    for _, _, files in os.walk(path):
        for filename in files:
            if filename.endswith(".py"):
                return True
    return False


def _has_python_files_in_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    for entry in path.iterdir():
        if entry.is_file() and entry.suffix == ".py":
            return True
    return False


def _discover_targets_from_dir(
    targets_dir: Path,
    *,
    project_pattern: str,
    exclude_patterns: Iterable[str],
) -> List[Path]:
    if not targets_dir.exists():
        raise ConfigurationError(
            f"Targets directory does not exist: {targets_dir}",
            context=ErrorContext(file=str(targets_dir)),
            error_code="CONFIG_TARGETS_DIR_NOT_FOUND",
        )
    if not targets_dir.is_dir():
        raise ConfigurationError(
            f"Targets directory is not a directory: {targets_dir}",
            context=ErrorContext(file=str(targets_dir)),
            error_code="CONFIG_TARGETS_DIR_INVALID",
        )

    exclude_set = {p for p in exclude_patterns if p}
    candidates: List[Path] = []

    # When targets_dir points directly to a single project root with top-level
    # Python modules, treat it as one target instead of splitting subpackages.
    if _has_python_files_in_root(targets_dir):
        name = targets_dir.name
        if fnmatch.fnmatch(name, project_pattern) and not any(
            fnmatch.fnmatch(name, pat) for pat in exclude_set
        ):
            return [targets_dir]

    for entry in targets_dir.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        if not fnmatch.fnmatch(name, project_pattern):
            continue
        if any(fnmatch.fnmatch(name, pat) for pat in exclude_set):
            continue
        if not _has_python_files(entry):
            continue
        candidates.append(entry)

    return sorted(candidates, key=lambda p: str(p.resolve()))


def resolve_projects_config(
    config: Optional[Config] = None,
    *,
    source_path: Optional[str] = None,
    targets: Optional[List[str]] = None,
    targets_dir: Optional[str] = None,
    project_pattern: Optional[str] = None,
    exclude_patterns: Optional[List[str]] = None,
    env_target_path: Optional[str] = None,
) -> ProjectsConfig:
    if config is None:
        raise ValueError("Config is required for resolve_projects_config")

    src_path_value = source_path or config.projects.source_path or os.getcwd()
    source_path_norm = _normalize_path(str(src_path_value))

    pattern = project_pattern or config.projects.project_pattern or "*"
    exclude = exclude_patterns or config.projects.exclude_patterns

    target_paths: List[Path] = []

    if targets:
        target_paths = [_normalize_path(value) for value in targets]
    elif targets_dir:
        target_paths = _discover_targets_from_dir(
            _normalize_path(targets_dir),
            project_pattern=pattern,
            exclude_patterns=exclude,
        )
        if not target_paths:
            raise ConfigurationError(
                f"No valid targets found in targets_dir: {targets_dir}",
                context=ErrorContext(file=str(targets_dir)),
                error_code="CONFIG_TARGETS_DIR_EMPTY",
                suggestion=(
                    "Ensure subdirectories match project_pattern and "
                    "contain .py files."
                ),
            )
    else:
        projects_section = config.projects
        cfg_targets = projects_section.targets
        cfg_targets_dir = projects_section.targets_dir
        cfg_target_path = projects_section.target_path

        if cfg_targets:
            target_paths = [_normalize_path(value) for value in cfg_targets]
        elif cfg_targets_dir:
            target_paths = _discover_targets_from_dir(
                _normalize_path(str(cfg_targets_dir)),
                project_pattern=pattern,
                exclude_patterns=exclude,
            )
            if not target_paths:
                raise ConfigurationError(
                    "No valid targets found in targets_dir: " f"{cfg_targets_dir}",
                    context=ErrorContext(file=str(cfg_targets_dir)),
                    error_code="CONFIG_TARGETS_DIR_EMPTY",
                    suggestion=(
                        "Ensure subdirectories match project_pattern and "
                        "contain .py files."
                    ),
                )
        elif cfg_target_path:
            target_paths = [_normalize_path(str(cfg_target_path))]
        elif env_target_path:
            target_paths = [_normalize_path(env_target_path)]

    if not target_paths:
        raise ConfigurationError(
            "No target projects configured.",
            context=ErrorContext(),
            error_code="CONFIG_TARGETS_EMPTY",
            suggestion=(
                "Set [projects].targets, [projects].targets_dir, "
                "[projects].target_path, or PYTHON_ARCH_TARGET_PATH."
            ),
        )

    return ProjectsConfig(
        source_path=source_path_norm,
        targets=_resolve_target_ids(target_paths),
    )


__all__ = [
    "TargetSpec",
    "ProjectsConfig",
    "resolve_projects_config",
]
