from __future__ import annotations

import importlib
import inspect
import os
import sys
import time
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Optional

from pythonarchtesting.config.accessors import get_bool, get_int
from pythonarchtesting.constants import ImportConstants
from pythonarchtesting.infrastructure.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from ._typing import (
        EvidenceCache,
        FunctionRegistry,
        ProjectStateLike,
        ValidationStats,
    )

logger = get_logger(__name__)


class ProjectStateImportsMixin:
    """
    Import responsibilities:
    - initialize() sys.path management + state reset
    - register_reference_modules()
    - import_module()
    """

    target_project_path: str | None
    target_module_name: str | None
    reference_modules: list[str]
    imported_modules: dict[str, ModuleType]
    target_functions: FunctionRegistry
    import_order: list[str]
    validation_results: list[Any]
    validation_stats: ValidationStats
    source_entities: list[Any]
    target_entities: list[Any]
    source_non_matchable_entities: list[Any]
    target_non_matchable_entities: list[Any]
    source_index: Any
    target_index: Any
    source_by_id: dict[str, Any]
    target_by_id: dict[str, Any]
    match_results: list[Any]
    match_by_source_id: dict[str, Any]
    match_registry: dict[str, Any]
    rules: list[Any]
    rule_results: list[Any]
    _static_evidence_cache: EvidenceCache | None
    _sys_path_inserted: str | None
    _import_stack: list[str]

    def initialize(
        self: "ProjectStateLike",
        target_project_path: str,
        target_module_name: Optional[str] = None,
    ) -> "ProjectStateLike":
        """
        Initialize the project state with a target project path.
        """
        normalized_path = os.path.abspath(target_project_path)
        if self._sys_path_inserted and self._sys_path_inserted in sys.path:
            if self._sys_path_inserted != normalized_path:
                sys.path.remove(self._sys_path_inserted)
        self._sys_path_inserted = None

        self.target_project_path = normalized_path
        self.target_module_name = target_module_name
        self.reference_modules = []
        self.imported_modules = {}
        self.target_functions = {}
        self.import_order = []
        self.validation_results = []
        self.validation_stats = {}
        self.source_entities = []
        self.target_entities = []
        self.source_non_matchable_entities = []
        self.target_non_matchable_entities = []
        self.source_index = None
        self.target_index = None
        self.source_by_id = {}
        self.target_by_id = {}
        self.match_results = []
        self.match_by_source_id = {}
        self.match_registry = {}
        self.rules = []
        self.rule_results = []
        self._static_evidence_cache = None

        self.module_discovery.set_target_path(self.target_project_path)

        logger.info(f"Initializing project state: {self.target_project_path}")

        if self.target_project_path and self.target_project_path not in sys.path:
            sys.path.insert(0, self.target_project_path)
            self._sys_path_inserted = self.target_project_path

        return self

    def register_reference_modules(
        self: "ProjectStateLike", *module_paths: str
    ) -> "ProjectStateLike":
        """
        Register reference module paths to be imported.
        """
        for module_path in module_paths:
            if module_path and module_path not in self.reference_modules:
                self.reference_modules.append(module_path)

        self.reference_modules = sorted(set(self.reference_modules))
        if self.reference_modules:
            self._set_import_order(self.import_order + self.reference_modules)

        if self.target_project_path:
            cfg = self._active_config()
            max_modules: int | None = get_int(cfg, "import", "max_modules", None)
            show_warnings: bool | None = get_bool(
                cfg, "import", "show_import_warnings", None
            )

            if max_modules is None:
                max_modules = ImportConstants.MAX_MODULES_DEFAULT

            to_import = list(self.reference_modules)
            if len(to_import) > max_modules:
                if show_warnings:
                    print(
                        f"Warning: Attempting to import {len(to_import)} modules, "
                        f"which exceeds the configured limit of {max_modules}."
                    )
                    print(f"Only the first {max_modules} modules will be imported.")
                to_import = to_import[:max_modules]

            for module_path in to_import:
                self.import_module(module_path)

        return self

    def validate_functions(
        self: "ProjectStateLike",
        validate_func: Callable[[Callable[..., Any], str], Any],
    ) -> dict[str, Any]:
        """
        Validate discovered target functions sequentially.

        Returns a compatibility dictionary with aggregate counts, timing, and
        per-function results keyed as ``<module_path>.<function_name>``.
        """
        functions_to_validate: list[tuple[Callable[..., Any], str]] = []

        for module_path, funcs in self.target_functions.items():
            functions_to_validate.extend((func, module_path) for func in funcs)

        if not functions_to_validate:
            return {
                "results": {},
                "errors": {},
                "success_count": 0,
                "failed_count": 0,
                "execution_time": 0.0,
            }

        start_time = time.time()
        results: dict[str, Any] = {}
        errors: dict[str, Exception] = {}

        for func, module_path in functions_to_validate:
            func_name = getattr(func, "__name__", "unknown")
            func_key = f"{module_path}.{func_name}"
            try:
                result = validate_func(func, module_path)
                results[func_key] = result
                if hasattr(result, "status") and hasattr(result, "check_type"):
                    self.add_validation_result(result)
            except Exception as exc:  # pragma: no cover - defensive
                errors[func_key] = exc

        return {
            "results": results,
            "errors": errors,
            "success_count": len(results),
            "failed_count": len(errors),
            "execution_time": time.time() - start_time,
        }

    def _continue_on_import_error(self: "ProjectStateLike") -> bool:
        cfg = self._active_config()
        value = get_bool(cfg, "error_handling", "continue_on_import_error", None)
        if value is None:
            value = get_bool(cfg, "import", "continue_on_import_error", True)
        return bool(value) if value is not None else True

    def import_module(self: "ProjectStateLike", module_path: str) -> ModuleType | None:
        """
        Import a module by its path.
        """
        project_modules = self.imported_modules

        if module_path in project_modules:
            self.memory_manager.track_module_usage(module_path)
            return project_modules[module_path]

        if (
            self.memory_manager.lazy_loading_enabled
            and self.memory_manager.should_defer_import(module_path)
        ):
            logger.debug(f"Deferring import of module: {module_path}")
            return None

        import_stack = self._import_stack
        if module_path in import_stack:
            from pythonarchtesting.exceptions import (
                ErrorContext,
            )
            from pythonarchtesting.exceptions import ImportError as FrameworkImportError

            error = FrameworkImportError(
                "Circular import detected: "
                f"{module_path} (import stack: {' -> '.join(import_stack)})",
                context=ErrorContext(module=module_path),
                error_code="CIRCULAR_IMPORT",
                suggestion="Check for circular dependencies in your module imports",
            )
            logger.warning(str(error))
            return None

        self._import_stack.append(module_path)

        try:
            module = importlib.import_module(module_path)
            project_modules[module_path] = module
            self.imported_modules = project_modules

            self.memory_manager.track_module_usage(module_path)

            self.target_functions[module_path] = [
                func for _, func in inspect.getmembers(module, inspect.isfunction)
            ]
            if module_path not in self.import_order:
                self._set_import_order(self.import_order + [module_path])

            return module
        except ImportError as e:
            from pythonarchtesting.exceptions import (
                ErrorContext,
            )
            from pythonarchtesting.exceptions import ImportError as FrameworkImportError

            context = ErrorContext(module=module_path)
            error = FrameworkImportError(
                f"Failed to import module '{module_path}': {e}",
                context=context,
                original_error=e,
                error_code="MODULE_IMPORT_FAILED",
                suggestion="Check if the module path is correct and dependencies are installed.",
            )

            show_warnings: bool | None = get_bool(
                self._active_config(), "import", "show_import_warnings", None
            )
            if show_warnings is not False:
                logger.error(str(error))
                if self._continue_on_import_error():
                    return None
                raise error
            return None
        except Exception as e:  # pragma: no cover - defensive
            from pythonarchtesting.exceptions import (
                ErrorContext,
            )
            from pythonarchtesting.exceptions import ImportError as FrameworkImportError

            context = ErrorContext(module=module_path)
            error = FrameworkImportError(
                f"Unexpected error importing '{module_path}': {str(e)}",
                context=context,
                original_error=e,
                error_code="UNEXPECTED_IMPORT_ERROR",
            )
            logger.error(str(error))
            if not self._continue_on_import_error():
                raise error
            return None
        finally:
            if self._import_stack:
                self._import_stack.pop()

    def _set_import_order(self: "ProjectStateLike", module_paths: list[str]) -> None:
        """Store deterministic import order."""
        self.import_order = sorted(set(module_paths))
