from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

from pythonarchtesting.infrastructure.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from ._typing import FunctionsStateLike

logger = get_logger(__name__)


class ProjectStateFunctionsMixin:
    """Function lookup and reference function resolution."""

    def get_function(
        self: "FunctionsStateLike", function_name: str
    ) -> Optional[Callable[..., Any]]:
        """
        Get a registered function by name, ignoring module.
        """
        import_order = self._stores.imports.import_order
        target_functions = self._stores.imports.target_functions

        for module_path in import_order:
            functions = target_functions.get(module_path, [])
            for func_item in functions:
                if (
                    hasattr(func_item, "__name__")
                    and func_item.__name__ == function_name
                ):
                    return cast(Callable[..., Any], func_item)

        for functions in target_functions.values():
            for func_item in functions:
                if (
                    hasattr(func_item, "__name__")
                    and func_item.__name__ == function_name
                ):
                    return cast(Callable[..., Any], func_item)

        return None

    def find_reference_function(
        self: "FunctionsStateLike",
        func: Callable[..., Any],
        module: Optional[str] = None,
    ) -> Optional[Callable[..., Any]]:
        """
        Find the reference implementation of a function.
        """
        func_name = func.__name__
        src_module = getattr(func, "__module__", None)
        src_qualname = getattr(func, "__qualname__", None)
        return cast(
            Optional[Callable[..., Any]],
            self.find_reference_function_str(
                func_name,
                target_module=module,
                src_module=src_module,
                src_qualname=src_qualname,
            ),
        )

    def find_reference_function_str(
        self: "FunctionsStateLike",
        func_name: str,
        target_module: Optional[str] = None,
        src_module: Optional[str] = None,
        src_qualname: Optional[str] = None,
    ) -> Optional[Callable[..., Any]]:
        """
        Find the reference implementation of a function.
        """
        return cast(
            Optional[Callable[..., Any]],
            self._find_reference(func_name, target_module, src_module, src_qualname),
        )

    def _find_reference(
        self: "FunctionsStateLike",
        func_name: str,
        target_module: Optional[str],
        src_module: Optional[str],
        src_qualname: Optional[str],
    ) -> Optional[Callable[..., Any]]:
        project_modules = self._stores.imports.imported_modules
        project_functions = self._stores.imports.target_functions
        reference_modules = self._context.reference_modules
        import_order = self._stores.imports.import_order

        logger.debug(
            "Looking for function '%s' in '%s'",
            func_name,
            target_module or "reference/import order",
        )

        candidate_modules: list[str] = []
        sources = (
            ([target_module] if target_module else [])
            + reference_modules
            + import_order
            + sorted(project_modules.keys())
        )
        for module_path in sources:
            if module_path and module_path not in candidate_modules:
                candidate_modules.append(module_path)

        candidates: list[tuple[str, Callable[..., Any]]] = []

        for module_path in candidate_modules:
            module_obj = project_modules.get(module_path)
            if module_obj is None:
                module_obj = self.import_module(module_path)
                if module_obj is None:
                    continue

            if module_path not in project_functions:
                project_functions[module_path] = [
                    func
                    for _, func in inspect.getmembers(module_obj, inspect.isfunction)
                ]

            for func in project_functions.get(module_path, []):
                if hasattr(func, "__name__") and func.__name__ == func_name:
                    candidates.append((module_path, func))

        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0][1]

        if src_module and src_qualname:
            for module_path, func in candidates:
                if (
                    module_path == src_module
                    and getattr(func, "__qualname__", None) == src_qualname
                ):
                    return func

        def key(item: tuple[str, Callable[..., Any]]) -> tuple[Any, str]:
            module_path, func = item
            dist = self._module_distance(module_path, src_module)
            qualname = getattr(func, "__qualname__", func.__name__)
            return (dist, f"{module_path}:{qualname}")

        return sorted(candidates, key=key)[0][1]

    def _module_distance(
        self: "FunctionsStateLike", a: str, b: Optional[str]
    ) -> tuple[int, int]:
        if not b:
            return (10**9, 0)
        a_parts = a.split(".")
        b_parts = b.split(".")
        common = 0
        for x, y in zip(a_parts, b_parts):
            if x != y:
                break
            common += 1
        return (len(a_parts) + len(b_parts) - 2 * common, -common)
