from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Protocol

from src.constants import ValidationConstants
from src.state.discovery import ModuleDiscovery
from src.state.memory_manager import MemoryManager
from src.state.validation import ValidationResult

if TYPE_CHECKING:
    from pathlib import Path

    from src.config import Config
    from src.entities import Entity, EntityIndex
    from src.matching import MatchResult
    from src.core.models import Rule, RuleResult

FunctionLike = Callable[..., Any]
FunctionRegistry = dict[str, list[FunctionLike]]
ValidationStats = dict[str, dict[ValidationConstants.ValidationStatus, int]]
EvidenceCache = dict[str, list[Any]]


class ProjectStateLike(Protocol):
    config: Config | None
    target_project_path: str | None
    reference_modules: list[str]
    validation_scope: str
    target_module_name: str | None
    imported_modules: dict[str, ModuleType]
    target_functions: FunctionRegistry
    import_order: list[str]
    validation_results: list[ValidationResult]
    validation_stats: ValidationStats
    source_entities: list[Entity]
    target_entities: list[Entity]
    source_non_matchable_entities: list[Entity]
    target_non_matchable_entities: list[Entity]
    source_index: EntityIndex | None
    target_index: EntityIndex | None
    source_by_id: dict[str, Entity]
    target_by_id: dict[str, Entity]
    match_results: list[MatchResult]
    match_by_source_id: dict[str, MatchResult]
    match_registry: dict[str, MatchResult]
    rules: list[Rule]
    rule_results: list[RuleResult]
    _static_evidence_cache: EvidenceCache | None
    _sys_path_inserted: str | None
    _import_stack: list[str]
    memory_manager: MemoryManager
    module_discovery: ModuleDiscovery

    def add_validation_result(self, result: ValidationResult) -> None: ...

    def import_module(self, module_path: str) -> ModuleType | None: ...

    def _active_config(self) -> Config: ...

    def _set_import_order(self, module_paths: list[str]) -> None: ...

    def _discover_python_files(self, root_path: Path) -> list[Path]: ...

    def _resolve_source_module_files(self, module_path: str) -> list[Path]: ...

    def _continue_on_import_error(self) -> bool: ...

    def find_reference_function_str(
        self,
        func_name: str,
        target_module: str | None = None,
        src_module: str | None = None,
        src_qualname: str | None = None,
    ) -> FunctionLike | None: ...

    def _find_reference(
        self,
        func_name: str,
        target_module: str | None,
        src_module: str | None,
        src_qualname: str | None,
    ) -> FunctionLike | None: ...

    def _module_distance(self, a: str, b: str | None) -> tuple[int, int]: ...

    def build_entity_indexes(self) -> None: ...

    def run_matching(self) -> None: ...

    def compile_rules(self) -> None: ...

    def evaluate_rules(self) -> None: ...
