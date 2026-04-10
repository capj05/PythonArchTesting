from __future__ import annotations

import importlib
import inspect
import os
import sys
import time
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

from pythonarchtesting.config.accessors import get_bool, get_int
from pythonarchtesting.constants import ImportConstants
from pythonarchtesting.infrastructure.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from ._typing import ImportsStateLike

logger = get_logger(__name__)


class ProjectStateImportsMixin:
    """
    Import responsibilities:
    - initialize() sys.path management + state reset
    - register_reference_modules()
    - import_module()
    """

    def initialize(
        self: "ImportsStateLike",
        target_project_path: str,
        target_module_name: Optional[str] = None,
    ) -> "ImportsStateLike":
        """
        Initialize the project state with a target project path.
        """
        normalized_path = os.path.abspath(target_project_path)
        if self._stores.imports.sys_path_inserted in sys.path:
            current_path = self._stores.imports.sys_path_inserted
            if current_path and current_path != normalized_path:
                sys.path.remove(current_path)

        self._stores.reset_imports()
        self._stores.reset_validation()
        self._stores.reset_analysis()
        self._stores.reset_evidence()
        self._replace_context(
            target_project_path=normalized_path,
            target_module_name=target_module_name,
            reference_modules=[],
        )

        self._services.module_discovery.set_target_path(self.target_project_path)

        logger.info("Initializing project state: %s", self.target_project_path)

        if self.target_project_path and self.target_project_path not in sys.path:
            sys.path.insert(0, self.target_project_path)
            self._stores.imports.sys_path_inserted = self.target_project_path

        return self

    def register_reference_modules(
        self: "ImportsStateLike", *module_paths: str
    ) -> "ImportsStateLike":
        """
        Register reference module paths to be imported.
        """
        updated_modules = list(self.reference_modules)
        for module_path in module_paths:
            if module_path and module_path not in updated_modules:
                updated_modules.append(module_path)

        self.reference_modules = sorted(set(updated_modules))
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
        self: "ImportsStateLike",
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

    def _continue_on_import_error(self: "ImportsStateLike") -> bool:
        cfg = self._active_config()
        value = get_bool(cfg, "error_handling", "continue_on_import_error", None)
        if value is None:
            value = get_bool(cfg, "import", "continue_on_import_error", True)
        return bool(value) if value is not None else True

    def import_module(self: "ImportsStateLike", module_path: str) -> ModuleType | None:
        """
        Import a module by its path.
        """
        project_modules = self.imported_modules

        if module_path in project_modules:
            self.memory_manager.track_module_usage(module_path)
            return cast(ModuleType, project_modules[module_path])

        if (
            self.memory_manager.lazy_loading_enabled
            and self.memory_manager.should_defer_import(module_path)
        ):
            logger.debug("Deferring import of module: %s", module_path)
            return None

        import_stack = self._stores.imports.import_stack
        if module_path in import_stack:
            from pythonarchtesting.exceptions import ErrorContext
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

        import_stack.append(module_path)

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
        except ImportError as exc:
            from pythonarchtesting.exceptions import ErrorContext
            from pythonarchtesting.exceptions import ImportError as FrameworkImportError

            context = ErrorContext(module=module_path)
            error = FrameworkImportError(
                f"Failed to import module '{module_path}': {exc}",
                context=context,
                original_error=exc,
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
        except Exception as exc:  # pragma: no cover - defensive
            from pythonarchtesting.exceptions import ErrorContext
            from pythonarchtesting.exceptions import ImportError as FrameworkImportError

            context = ErrorContext(module=module_path)
            error = FrameworkImportError(
                f"Unexpected error importing '{module_path}': {str(exc)}",
                context=context,
                original_error=exc,
                error_code="UNEXPECTED_IMPORT_ERROR",
            )
            logger.error(str(error))
            if not self._continue_on_import_error():
                raise error
            return None
        finally:
            if import_stack:
                import_stack.pop()

    def _set_import_order(self: "ImportsStateLike", module_paths: list[str]) -> None:
        """Store deterministic import order."""
        self.import_order = sorted(set(module_paths))
