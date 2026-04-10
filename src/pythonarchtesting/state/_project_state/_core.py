from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, cast

from pythonarchtesting.config import Config, load_config
from pythonarchtesting.constants import ValidationConstants
from pythonarchtesting.infrastructure.logging import get_logger
from pythonarchtesting.state.discovery import ModuleDiscovery
from pythonarchtesting.state.memory_manager import MemoryManager

from ._context import ProjectContext
from ._stores import ProjectServices, ProjectStores
from .entities import ProjectStateEntitiesMixin
from .evidence import ProjectStateEvidenceMixin
from .functions import ProjectStateFunctionsMixin
from .imports import ProjectStateImportsMixin
from .rules_engine import ProjectStateRulesMixin

if TYPE_CHECKING:
    from pythonarchtesting.state.validation import ValidationResult

ValidationStatus = ValidationConstants.ValidationStatus
logger = get_logger(__name__)


def _context_property(name: str, *, rebuild_services: bool = False) -> property:
    def getter(self: "ProjectState") -> Any:
        return getattr(self._context, name)

    def setter(self: "ProjectState", value: Any) -> None:
        self._replace_context(**{name: value})
        if rebuild_services:
            self._rebuild_services(value)

    return property(getter, setter)


def _store_property(store_name: str, field_name: str) -> property:
    def getter(self: "ProjectState") -> Any:
        return getattr(getattr(self._stores, store_name), field_name)

    def setter(self: "ProjectState", value: Any) -> None:
        setattr(getattr(self._stores, store_name), field_name, value)

    return property(getter, setter)


class ProjectState(
    ProjectStateImportsMixin,
    ProjectStateFunctionsMixin,
    ProjectStateEntitiesMixin,
    ProjectStateEvidenceMixin,
    ProjectStateRulesMixin,
):
    """
    State manager for storing project information (single-target only).
    """

    config = _context_property("config", rebuild_services=True)
    target_project_path = _context_property("target_project_path")
    reference_modules = _context_property("reference_modules")
    validation_scope = _context_property("validation_scope")
    target_module_name = _context_property("target_module_name")

    imported_modules = _store_property("imports", "imported_modules")
    target_functions = _store_property("imports", "target_functions")
    import_order = _store_property("imports", "import_order")
    validation_results = _store_property("validation", "validation_results")
    validation_stats = _store_property("validation", "validation_stats")
    source_entities = _store_property("entities", "source_entities")
    target_entities = _store_property("entities", "target_entities")
    source_non_matchable_entities = _store_property(
        "entities", "source_non_matchable_entities"
    )
    target_non_matchable_entities = _store_property(
        "entities", "target_non_matchable_entities"
    )
    source_index = _store_property("entities", "source_index")
    target_index = _store_property("entities", "target_index")
    source_by_id = _store_property("entities", "source_by_id")
    target_by_id = _store_property("entities", "target_by_id")
    match_results = _store_property("matches", "match_results")
    match_by_source_id = _store_property("matches", "match_by_source_id")
    match_registry = _store_property("matches", "match_registry")
    rules = _store_property("rules", "rules")
    rule_results = _store_property("rules", "rule_results")

    def __init__(
        self,
        target_path: str,
        reference_modules: list[str],
        config: Optional[Config] = None,
        validation_scope: str = "all",
    ) -> None:
        self._initialized = False

        logger.info("Initializing project state...")

        self._state_lock = threading.RLock()
        self._context = ProjectContext(
            config=config,
            target_project_path=target_path,
            reference_modules=list(reference_modules),
            validation_scope=validation_scope,
            target_module_name=None,
        )
        self._stores = ProjectStores()
        self._services = self._build_services(config)

        self._initialized = True

    @property
    def _static_evidence_cache(self) -> Any:
        return self._stores.evidence.static_evidence_cache

    @_static_evidence_cache.setter
    def _static_evidence_cache(self, value: Any) -> None:
        self._stores.evidence.static_evidence_cache = value

    @property
    def _import_stack(self) -> list[str]:
        return self._stores.imports.import_stack

    @_import_stack.setter
    def _import_stack(self, value: list[str]) -> None:
        self._stores.imports.import_stack = value

    @property
    def _sys_path_inserted(self) -> str | None:
        return self._stores.imports.sys_path_inserted

    @_sys_path_inserted.setter
    def _sys_path_inserted(self, value: str | None) -> None:
        self._stores.imports.sys_path_inserted = value

    @property
    def memory_manager(self) -> MemoryManager:
        return self._services.memory_manager

    @memory_manager.setter
    def memory_manager(self, value: MemoryManager) -> None:
        self._services.memory_manager = value

    @property
    def module_discovery(self) -> ModuleDiscovery:
        return self._services.module_discovery

    @module_discovery.setter
    def module_discovery(self, value: ModuleDiscovery) -> None:
        self._services.module_discovery = value
        self._sync_service_target_path()

    def _build_services(self, config: Config | None) -> ProjectServices:
        module_discovery = ModuleDiscovery(
            path=self._context.target_project_path,
            config=config,
        )
        return ProjectServices(
            memory_manager=MemoryManager(config=config),
            module_discovery=module_discovery,
        )

    def _sync_service_target_path(self) -> None:
        self._services.module_discovery.set_target_path(
            self._context.target_project_path
        )

    def _replace_context(self, **changes: Any) -> ProjectContext:
        self._context = replace(self._context, **changes)
        self._sync_service_target_path()
        return self._context

    def _rebuild_services(self, config: Config | None = None) -> None:
        self._services = self._build_services(
            config if config is not None else self.config
        )

    def _ensure_context_config(self) -> ProjectContext:
        if self._context.config is None:
            config = load_config()
            self._replace_context(config=config)
            self._rebuild_services(config)
        return self._context

    def add_validation_result(self, result: ValidationResult) -> None:
        """Add a validation result to the state with thread safety."""
        with self._state_lock:
            self.validation_results.append(result)
            status = result.status
            check_type = result.check_type
            if check_type not in self.validation_stats:
                self.validation_stats[check_type] = {}
            if status not in self.validation_stats[check_type]:
                self.validation_stats[check_type][status] = 0
            self.validation_stats[check_type][status] += 1

    def reset(self) -> "ProjectState":
        """Reset mutable runtime state while preserving configured target context."""
        target_path = self.target_project_path or "."
        target_module_name = self.target_module_name
        self.initialize(target_path, target_module_name)
        return self

    def get_validation_results(
        self,
        check_type: Optional[str] = None,
        status: Optional[ValidationConstants.ValidationStatus] = None,
        function_name: Optional[str] = None,
    ) -> list[ValidationResult]:
        """
        Get validation results, optionally filtered by type, status, or function.
        """
        results = cast(list[ValidationResult], self.validation_results)

        if check_type:
            results = [r for r in results if r.check_type == check_type]
        if status:
            results = [r for r in results if r.status == status]
        if function_name:
            results = [r for r in results if r.src_function_name == function_name]

        return results

    def get_validation_summary(self) -> dict[str, dict[str, int]]:
        """Get a summary of validation results by check type and status."""
        return {
            check_type: {status.value: count for status, count in stats.items()}
            for check_type, stats in self.validation_stats.items()
        }

    def discover_modules(self) -> list[str]:
        """Delegate to module discovery component."""
        self._sync_service_target_path()
        modules = self.module_discovery.discover_modules()
        self._set_import_order(modules)
        return modules

    def _get_discovery_config(self) -> dict[str, Any]:
        """Return discovery settings for the configured target project."""
        self._sync_service_target_path()
        return self.module_discovery.get_discovery_config()

    def _get_module_file_path(
        self, module_name: str, target_path: Optional[str] = None
    ) -> Optional[str]:
        """Resolve a discovered module name to a file path."""
        active_target_path = target_path or self.target_project_path
        if active_target_path:
            return self.module_discovery.get_module_file_path(
                module_name, Path(active_target_path)
            )
        return None

    def cleanup_unused_modules(
        self, min_usage: int = 0, max_age_hours: float = 24.0
    ) -> int:
        """Delegate unused module cleanup to the memory manager."""
        return self.memory_manager.cleanup_unused_modules(
            self.imported_modules, self.target_functions, min_usage, max_age_hours
        )

    def cleanup_old_results(self, max_results: Optional[int] = None) -> int:
        """Delegate validation result cleanup to the memory manager."""
        return self.memory_manager.cleanup_old_results(
            self.validation_results, max_results
        )

    def clear_validation_results(self) -> None:
        """Clear validation results and accumulated stats."""
        self._stores.reset_validation()

    def get_memory_stats(self) -> dict[str, Any]:
        """Return memory statistics for the current state."""
        return self.memory_manager.get_memory_stats(
            self.imported_modules, self.target_functions, self.validation_results
        )


__all__ = ["ProjectState"]
