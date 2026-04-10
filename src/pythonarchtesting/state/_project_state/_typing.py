from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol

from pythonarchtesting.constants import ValidationConstants

from ._context import ProjectContext
from ._stores import ProjectServices, ProjectStores

if TYPE_CHECKING:
    from pathlib import Path

    from pythonarchtesting.config import Config
    from pythonarchtesting.state.validation import ValidationResult

FunctionLike = Callable[..., Any]
FunctionRegistry = dict[str, list[FunctionLike]]
ValidationStats = dict[str, dict[ValidationConstants.ValidationStatus, int]]
EvidenceCache = dict[str, list[Any]]


class BaseStateLike(Protocol):
    _context: ProjectContext
    _stores: ProjectStores
    _services: ProjectServices

    def _ensure_context_config(self) -> ProjectContext: ...

    @property
    def memory_manager(self) -> Any: ...


class ImportsStateLike(BaseStateLike, Protocol):
    def _replace_context(self, **changes: Any) -> ProjectContext: ...

    def _active_config(self) -> Config: ...

    def add_validation_result(self, result: ValidationResult) -> None: ...

    def import_module(self, module_path: str) -> Any: ...

    def _set_import_order(self, module_paths: list[str]) -> None: ...

    def _continue_on_import_error(self) -> bool: ...

    @property
    def target_project_path(self) -> str | None: ...

    @property
    def target_module_name(self) -> str | None: ...

    @property
    def reference_modules(self) -> list[str]: ...

    @reference_modules.setter
    def reference_modules(self, value: list[str]) -> None: ...

    @property
    def import_order(self) -> list[str]: ...

    @import_order.setter
    def import_order(self, value: list[str]) -> None: ...

    @property
    def imported_modules(self) -> dict[str, Any]: ...

    @imported_modules.setter
    def imported_modules(self, value: dict[str, Any]) -> None: ...

    @property
    def target_functions(self) -> FunctionRegistry: ...

    @target_functions.setter
    def target_functions(self, value: FunctionRegistry) -> None: ...


class FunctionsStateLike(BaseStateLike, Protocol):
    def import_module(self, module_path: str) -> Any: ...

    def find_reference_function_str(
        self,
        func_name: str,
        target_module: str | None = None,
        src_module: str | None = None,
        src_qualname: str | None = None,
    ) -> Any: ...

    def _find_reference(
        self,
        func_name: str,
        target_module: str | None,
        src_module: str | None,
        src_qualname: str | None,
    ) -> Any: ...

    def _module_distance(self, a: str, b: str | None) -> tuple[int, int]: ...


class EntitiesStateLike(BaseStateLike, Protocol):
    def add_validation_result(self, result: ValidationResult) -> None: ...

    def _discover_python_files(self, root_path: Path) -> list[Path]: ...

    def _resolve_source_module_files(self, module_path: str) -> list[Path]: ...


class RulesStateLike(BaseStateLike, Protocol):
    def add_validation_result(self, result: ValidationResult) -> None: ...


class EvidenceStateLike(BaseStateLike, Protocol):
    def _active_config(self) -> Config: ...


class MatchStateLike(BaseStateLike, Protocol):
    @property
    def source_by_id(self) -> dict[str, Any]: ...

    @property
    def target_index(self) -> Any: ...


__all__ = [
    "BaseStateLike",
    "EvidenceCache",
    "EvidenceStateLike",
    "FunctionLike",
    "FunctionRegistry",
    "FunctionsStateLike",
    "ImportsStateLike",
    "MatchStateLike",
    "ProjectContext",
    "ProjectServices",
    "ProjectStores",
    "RulesStateLike",
    "ValidationStats",
]
