"""Runner source preparation."""

from __future__ import annotations

import ast
import importlib.metadata
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.config.accessors import get_bool
from pythonarchtesting.entities import Entity, build_entity_index, sort_entities
from pythonarchtesting.entities_extraction import (
    extract_entities_from_ast_with_nonmatchable,
    root_path_from_module_path,
)
from pythonarchtesting.exceptions import ConfigurationError, ErrorContext
from pythonarchtesting.principles.task import bind_task, is_task, load_task
from pythonarchtesting.rules.compilation.orchestrator import compile_rules
from pythonarchtesting.run_state import RunState
from pythonarchtesting.state import ValidationResult, ValidationStatus
from pythonarchtesting.state.source_resolution import resolve_source_module_files
from pythonarchtesting.state.validation import (
    compiler_evidence_to_validation,
    rule_result_to_validation,
)
from pythonarchtesting.util.discovery_utils import discover_python_files
from pythonarchtesting.validation_scope import (
    VALIDATION_SCOPE_ALL,
    filter_entities_for_scope,
)


def _framework_version() -> str:
    try:
        return importlib.metadata.version("pythonarchtesting")
    except Exception:
        return "unknown"


def _resolve_source_module_files(
    module_path: str,
    source_path: Path,
    prefer_stub_files: bool,
) -> Tuple[List[Path], List[ValidationResult]]:
    return resolve_source_module_files(
        module_path,
        source_path,
        prefer_stub_files=prefer_stub_files,
    )


def _prefers_stub_reference_files(config: Config) -> bool:
    patterns = tuple(config.discovery.included_file_patterns)
    return bool(patterns) and set(patterns) == {"*.pyi"}


def _resolve_reference_modules(
    reference_modules: Optional[List[str]],
) -> List[str]:
    if reference_modules:
        return [m.strip() for m in reference_modules if m and m.strip()]
    env_value = os.environ.get("PYTHON_ARCH_REFERENCE_MODULES", "")
    if env_value:
        return [m.strip() for m in env_value.split(",") if m.strip()]
    return []


def _require_existing_source(source_path: Path) -> None:
    """Fail loudly when the reference project path is not there at all.

    Without this, a mistyped ``--source`` produces an empty run that reports no
    violations and exits 0 — a typo would look like a clean pass.
    """
    if not source_path.exists():
        raise ConfigurationError(
            f"Source path does not exist: {source_path}",
            context=ErrorContext(file=str(source_path)),
            error_code="CONFIG_SOURCE_NOT_FOUND",
            suggestion="Point --source at the reference project directory.",
        )


def _require_discoverable_source(source_path: Path, config: Config) -> None:
    """Fail when discovery finds nothing to read.

    Only meaningful for the discovery branch; when ``reference_modules`` names the
    modules explicitly, unresolvable ones are already reported per module.
    """
    if not any(discover_python_files(source_path, config)):
        raise ConfigurationError(
            f"No Python files found in source path: {source_path}",
            context=ErrorContext(file=str(source_path)),
            error_code="CONFIG_SOURCE_EMPTY",
            suggestion=(
                "Check --source and the [discovery] included_file_patterns setting."
            ),
        )


def prepare_source(
    *,
    config: Config,
    source_path: Path,
    reference_modules: Optional[List[str]] = None,
    validation_scope: str = VALIDATION_SCOPE_ALL,
    _source_root_label: str = "source",
    architecture: bool = False,
) -> RunState:
    _require_existing_source(source_path)
    task = None
    if is_task(source_path):
        # A task directory: its task.toml binds a catalogue principle to the
        # unannotated reference, whose entities get the declarations below.
        task = load_task(source_path)
        source_path = task.reference
    include_nested = get_bool(config, "matching", "include_nested_functions", False)
    source_entities: List[Entity] = []
    source_errors: List[ValidationResult] = []

    resolved_modules = _resolve_reference_modules(reference_modules)
    if resolved_modules:
        resolved_modules = sorted(set(resolved_modules))

    if resolved_modules:
        prefer_stub_files = _prefers_stub_reference_files(config)
        for module_path in resolved_modules:
            files, errors = _resolve_source_module_files(
                module_path,
                source_path,
                prefer_stub_files,
            )
            source_errors.extend(errors)
            for file_path in files:
                root_path = root_path_from_module_path(module_path, Path(file_path))
                try:
                    file_text = Path(file_path).read_text(
                        encoding="utf-8", errors="replace"
                    )
                    tree = ast.parse(file_text)
                except SyntaxError as exc:
                    source_errors.append(
                        ValidationResult(
                            status=ValidationStatus.ERROR,
                            description="Syntax error while parsing source module.",
                            check_type="extraction/syntax_error",
                            src_function_name="",
                            src_package=module_path,
                            src_file=str(file_path),
                            src_line_num=getattr(exc, "lineno", None),
                            details={
                                "exception": str(exc),
                                "lineno": getattr(exc, "lineno", None),
                                "offset": getattr(exc, "offset", None),
                            },
                        )
                    )
                    continue

                matchable, _ = extract_entities_from_ast_with_nonmatchable(
                    tree,
                    file_text,
                    Path(file_path),
                    root_path,
                    None,
                    role="source",
                    include_nested_functions=include_nested,
                    root_label=_source_root_label,
                )
                source_entities.extend(matchable)
    else:
        _require_discoverable_source(source_path, config)
        for file_path in discover_python_files(source_path, config):
            try:
                file_text = Path(file_path).read_text(
                    encoding="utf-8", errors="replace"
                )
                tree = ast.parse(file_text)
            except SyntaxError as exc:
                source_errors.append(
                    ValidationResult(
                        status=ValidationStatus.ERROR,
                        description="Syntax error while parsing source files.",
                        check_type="extraction/syntax_error",
                        src_function_name="",
                        src_package=str(source_path),
                        src_file=str(file_path),
                        src_line_num=getattr(exc, "lineno", None),
                        details={
                            "exception": str(exc),
                            "lineno": getattr(exc, "lineno", None),
                            "offset": getattr(exc, "offset", None),
                        },
                    )
                )
                continue

            matchable, _ = extract_entities_from_ast_with_nonmatchable(
                tree,
                file_text,
                Path(file_path),
                source_path,
                None,
                role="source",
                include_nested_functions=include_nested,
                root_label=_source_root_label,
            )
            source_entities.extend(matchable)

    source_entities = sort_entities(source_entities)
    if task is not None:
        source_entities, _ = bind_task(task, source_entities)
    source_entities = sort_entities(
        filter_entities_for_scope(source_entities, validation_scope)
    )
    source_index = build_entity_index(source_entities)
    source_by_id = {e.canonical_id: e for e in source_entities}

    rules: List[Any] = []
    compiler_results: List[Any] = []
    compiler_validations: List[ValidationResult] = []

    if source_entities and source_index:
        rules, compiler_evidence, compiler_results = compile_rules(
            source_entities, config, architecture=architecture
        )
        rule_by_id = {rule.rule_id: rule for rule in rules}
        for result in compiler_results:
            rule = rule_by_id.get(result.rule_id)
            source_entity = source_by_id.get(result.source_entity_id)
            if rule is None or source_entity is None:
                continue
            compiler_validations.append(
                rule_result_to_validation(rule, result, source_entity, None)
            )
        for evidence in compiler_evidence:
            source_entity = source_by_id.get(evidence.entity_id)
            if source_entity is None:
                continue
            compiler_validations.append(
                compiler_evidence_to_validation(evidence, source_entity)
            )

    compiler_validations.extend(source_errors)

    return RunState(
        config=config,
        source_path=source_path,
        reference_modules=resolved_modules,
        source_entities=source_entities,
        source_index=source_index,
        source_by_id=source_by_id,
        rules=rules,
        compiler_results=compiler_results,
        compiler_validations=compiler_validations,
        run_generated_at=datetime.now(timezone.utc),
        framework_version=_framework_version(),
        validation_scope=validation_scope,
        principle=task.principle.id if task is not None else None,
    )


SYNTAX_CHECK = "extraction/syntax_error"


@dataclass(frozen=True)
class Scan:
    """One extraction of ``path``: its ``entities`` and the core's
    ``validations`` (a file that does not parse is one), under the config file
    ``applied`` (``"defaults"`` without one, as ``resolve_config`` names it).

    A caller that needs a submission's entities in several steps reads them
    once (``extract``) and hands the ``Scan`` on; ``entities_of`` reads the
    source again only when a step would apply another config file."""

    path: Path
    applied: str
    entities: Tuple[Entity, ...]
    validations: Tuple[Any, ...]

    def syntax_errors(self) -> List[Any]:
        """The validations of the files that do not parse."""
        return [v for v in self.validations if v.check_type == SYNTAX_CHECK]


def extract(path: Path, loaded: Config, applied: str) -> Scan:
    """The extraction of ``path`` under the config ``loaded`` (the file
    ``applied``)."""
    state = prepare_source(config=loaded, source_path=Path(path))
    return Scan(
        Path(path),
        applied,
        tuple(state.source_entities),
        tuple(state.compiler_validations),
    )


def entities_of(
    path: Path, loaded: Config, applied: str, scanned: Optional[Scan]
) -> List[Entity]:
    """The entities of ``path`` under ``loaded`` (the file ``applied``):
    those of ``scanned`` when it is the same extraction (the same path, as
    given, and config file), else read now."""
    if (
        scanned is not None
        and scanned.applied == applied
        and scanned.path == Path(path)
    ):
        return list(scanned.entities)
    return list(extract(path, loaded, applied).entities)
