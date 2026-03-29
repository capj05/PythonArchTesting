"""
Shared source module resolution helpers.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from src.constants import ValidationConstants
from src.entities_extraction.paths import module_path_from_file
from src.state.validation import ValidationResult

ValidationStatus = ValidationConstants.ValidationStatus


def _candidate_module_paths(
    module_path: str,
    source_path: Optional[Path],
    prefer_stub_files: bool,
) -> Iterable[Path]:
    if source_path is None:
        return ()

    module_rel_path = Path(*module_path.split(".")) if module_path else Path()
    ordered_suffixes = (".pyi",) if prefer_stub_files else (".py", ".pyi")
    candidates: List[Path] = []
    for suffix in ordered_suffixes:
        candidates.append(source_path / module_rel_path.with_suffix(suffix))
    init_names = (
        ("__init__.pyi",)
        if prefer_stub_files
        else (
            "__init__.py",
            "__init__.pyi",
        )
    )
    for init_name in init_names:
        candidates.append(source_path / module_rel_path / init_name)
    return tuple(candidates)


def _resolve_from_source_path(
    module_path: str,
    source_path: Optional[Path],
    prefer_stub_files: bool,
) -> List[Path]:
    for candidate in _candidate_module_paths(
        module_path, source_path, prefer_stub_files
    ):
        if candidate.exists():
            return [candidate]
    return []


def _resolve_by_source_search(
    module_path: str,
    source_path: Optional[Path],
    prefer_stub_files: bool,
) -> List[Path]:
    if source_path is None or not source_path.exists():
        return []

    ordered_suffixes = (".pyi",) if prefer_stub_files else (".py", ".pyi")
    matches: List[Path] = []
    for suffix in ordered_suffixes:
        for candidate in sorted(source_path.rglob(f"*{suffix}")):
            resolved_module_path, _ = module_path_from_file(
                candidate, source_path, None
            )
            if resolved_module_path == module_path:
                matches.append(candidate)
        if matches:
            return matches
    return []


def _resolve_from_importlib(module_path: str) -> List[Path]:
    files: List[Path] = []
    spec = importlib.util.find_spec(module_path)

    if spec is None:
        return []

    if spec.origin and spec.origin not in {"built-in", "namespace"}:
        files.append(Path(spec.origin))

    if not files and spec.submodule_search_locations:
        for location in spec.submodule_search_locations:
            for init_name in ("__init__.py", "__init__.pyi"):
                init_path = Path(location) / init_name
                if init_path.exists():
                    files.append(init_path)
                    break
            if files:
                break

    return files


def resolve_source_module_files(
    module_path: str,
    source_path: Optional[Path] = None,
    prefer_stub_files: bool = False,
) -> Tuple[List[Path], List[ValidationResult]]:
    errors: List[ValidationResult] = []
    files = _resolve_from_source_path(module_path, source_path, prefer_stub_files)
    if not files:
        files = _resolve_by_source_search(module_path, source_path, prefer_stub_files)
    if not files and not (source_path is not None and prefer_stub_files):
        try:
            files = _resolve_from_importlib(module_path)
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(
                ValidationResult(
                    status=ValidationStatus.ERROR,
                    description="Failed to resolve source module spec.",
                    check_type="extraction/source_resolution",
                    src_function_name="",
                    src_package=module_path,
                    details={"error": str(exc)},
                )
            )
            return [], errors

    if not files:
        errors.append(
            ValidationResult(
                status=ValidationStatus.ERROR,
                description="Source module not found during resolution.",
                check_type="extraction/source_resolution",
                src_function_name="",
                src_package=module_path,
                details={"module": module_path},
            )
        )
        return [], errors

    if not files:
        errors.append(
            ValidationResult(
                status=ValidationStatus.ERROR,
                description="Source module resolved without file path.",
                check_type="extraction/source_resolution",
                src_function_name="",
                src_package=module_path,
                details={"module": module_path},
            )
        )

    return files, errors


__all__ = ["resolve_source_module_files"]
