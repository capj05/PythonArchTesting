from __future__ import annotations

import threading
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Optional

from pythonarchtesting.config import Config
from pythonarchtesting.constants import ValidationConstants
from pythonarchtesting.infrastructure.logging import get_logger
from pythonarchtesting.state.discovery import ModuleDiscovery
from pythonarchtesting.state.memory_manager import MemoryManager

from ._typing import EvidenceCache, FunctionRegistry, ValidationStats
from .entities import ProjectStateEntitiesMixin
from .evidence import ProjectStateEvidenceMixin
from .functions import ProjectStateFunctionsMixin
from .imports import ProjectStateImportsMixin
from .rules_engine import ProjectStateRulesMixin

if TYPE_CHECKING:
    from pythonarchtesting.core.models import Rule, RuleResult
    from pythonarchtesting.entities import Entity, EntityIndex
    from pythonarchtesting.matching import MatchResult
    from pythonarchtesting.state.validation import ValidationResult

ValidationStatus = ValidationConstants.ValidationStatus
logger = get_logger(__name__)


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

    def __init__(
        self,
        target_path: str,
        reference_modules: list[str],
        config: Optional[Config] = None,
        validation_scope: str = "all",
    ) -> None:
        self._initialized = False

        logger.info("Initializing project state...")

        # Store configuration
        self.config: Config | None = config
        self.target_project_path: str | None = target_path
        self.reference_modules: list[str] = list(reference_modules)
        self.validation_scope = validation_scope

        self._state_lock = threading.RLock()

        # Single-target configuration
        self.target_module_name: Optional[str] = None
        self.imported_modules: dict[str, ModuleType] = {}
        self.target_functions: FunctionRegistry = {}
        self.import_order: list[str] = []
        self._import_stack: list[str] = []

        # Modular components
        self.memory_manager = MemoryManager(config=config)
        self.module_discovery = ModuleDiscovery(config=config)

        # Validation
        self.validation_results: list[ValidationResult] = []
        self.validation_stats: ValidationStats = {}

        # Matching/entities/rules
        self.source_entities: list[Entity] = []
        self.target_entities: list[Entity] = []
        self.source_non_matchable_entities: list[Entity] = []
        self.target_non_matchable_entities: list[Entity] = []
        self.source_index: Optional[EntityIndex] = None
        self.target_index: Optional[EntityIndex] = None
        self.source_by_id: dict[str, Entity] = {}
        self.target_by_id: dict[str, Entity] = {}
        self.match_results: list[MatchResult] = []
        self.match_by_source_id: dict[str, MatchResult] = {}
        self.match_registry: dict[str, MatchResult] = {}
        self.rules: list[Rule] = []
        self.rule_results: list[RuleResult] = []

        # Evidence
        self._static_evidence_cache: EvidenceCache | None = None

        # sys.path tracking
        self._sys_path_inserted: Optional[str] = None

        self._initialized = True

    def add_validation_result(self, result: ValidationResult) -> None:
        """Add a validation result to the state with thread safety."""
        with self._state_lock:
            self.validation_results.append(result)
            # Keep existing stat updates by moving the old body here verbatim.
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
        results = self.validation_results

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

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-style accessor for backward compatibility."""
        return getattr(self, key, default)

    def discover_modules(self) -> list[str]:
        """Delegate to module discovery component."""
        if self.target_project_path:
            self.module_discovery.set_target_path(self.target_project_path)
        modules = self.module_discovery.discover_modules()
        self._set_import_order(modules)
        return modules

    def _get_discovery_config(self) -> dict[str, Any]:
        """Return discovery settings for the configured target project."""
        if self.target_project_path:
            self.module_discovery.set_target_path(self.target_project_path)
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
        self.validation_results = []
        self.validation_stats = {}

    def get_memory_stats(self) -> dict[str, Any]:
        """Return memory statistics for the current state."""
        return self.memory_manager.get_memory_stats(
            self.imported_modules, self.target_functions, self.validation_results
        )


__all__ = ["ProjectState"]
