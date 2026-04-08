"""
Memory management functionality for the project state.
Handles module usage tracking, cleanup, and memory optimization.
"""

import logging
import time
from typing import Any, Dict, Optional

from pythonarchtesting.config.accessors import get_bool, get_int
from pythonarchtesting.infrastructure.logging import get_logger

# Get logger for this module
logger = get_logger(__name__)


class MemoryManager:
    """
    Manages memory optimization for the project state.
    Handles module usage tracking and cleanup of unused resources.
    """

    def __init__(self, config: Optional[Any] = None) -> None:
        """Initialize the memory manager."""
        self._config = config
        self._module_usage: Dict[str, int] = {}
        self._module_last_access: Dict[str, float] = {}
        self._max_results = get_int(
            self._config, "memory", "max_validation_results", 10000
        )
        self._cleanup_enabled = get_bool(
            self._config, "memory", "cleanup_enabled", True
        )
        self._lazy_loading_enabled = get_bool(
            self._config, "memory", "lazy_loading", True
        )

    def track_module_usage(self, module_path: str) -> None:
        """
        Track module usage for memory optimization.

        Args:
            module_path: Path to the module being accessed
        """
        current_time = time.time()
        self._module_usage[module_path] = self._module_usage.get(module_path, 0) + 1
        self._module_last_access[module_path] = current_time

        # Debug logging for usage tracking
        if logger.isEnabledFor(logging.DEBUG):
            usage_count = self._module_usage[module_path]
            logger.debug(
                f"Module usage tracked: {module_path} (accessed {usage_count} times)"
            )

    def should_defer_import(self, module_path: str) -> bool:
        """
        Determine if a module import should be deferred based on usage patterns.

        Args:
            module_path: Path to the module to check

        Returns:
            True if import should be deferred, False otherwise
        """
        # For now, be conservative and don't defer imports
        # This can be enhanced with more sophisticated logic later
        return False

    def cleanup_unused_modules(
        self,
        imported_modules: Dict[str, Any],
        target_functions: Dict[str, Any],
        min_usage: int = 0,
        max_age_hours: float = 24.0,
    ) -> int:
        """
        Remove modules that haven't been used recently to free memory.

        Args:
            imported_modules: Dictionary of imported modules to modify
            target_functions: Dictionary of target functions to modify
            min_usage: Minimum usage count to keep a module
            max_age_hours: Maximum age in hours since last access

        Returns:
            Number of modules removed
        """
        if not self._cleanup_enabled:
            logger.debug("Module cleanup disabled")
            return 0

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        modules_to_remove = []

        for module_path, usage_count in self._module_usage.items():
            last_access = self._module_last_access.get(module_path, 0)

            # Remove if usage is too low or hasn't been accessed recently
            if (
                usage_count <= min_usage
                or (current_time - last_access) > max_age_seconds
            ):
                modules_to_remove.append(module_path)

        # Remove modules from memory
        removed_count = 0
        for module_path in modules_to_remove:
            try:
                # Remove from imported modules
                if module_path in imported_modules:
                    del imported_modules[module_path]

                # Remove from target functions
                if module_path in target_functions:
                    del target_functions[module_path]

                # Remove from usage tracking
                if module_path in self._module_usage:
                    del self._module_usage[module_path]
                if module_path in self._module_last_access:
                    del self._module_last_access[module_path]

                removed_count += 1
                logger.debug(f"Removed unused module from memory: {module_path}")

            except Exception as e:
                logger.warning(f"Failed to remove module {module_path}: {e}")

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} unused modules from memory")

        return removed_count

    def cleanup_old_results(
        self, validation_results: list, max_results: Optional[int] = None
    ) -> int:
        """
        Remove old validation results to free memory.

        Args:
            validation_results: List of validation results to modify
            max_results: Maximum number of results to keep (overrides config)

        Returns:
            Number of results removed
        """
        if not self._cleanup_enabled:
            logger.debug("Result cleanup disabled")
            return 0

        limit = max_results or self._max_results
        if limit is None or len(validation_results) <= limit:
            return 0

        excess_count = len(validation_results) - limit
        # Remove oldest results (keep most recent)
        validation_results[:] = validation_results[excess_count:]

        logger.debug(f"Cleaned up {excess_count} old validation results")
        return excess_count

    def get_memory_stats(
        self,
        imported_modules: Dict[str, Any],
        target_functions: Dict[str, Any],
        validation_results: list,
    ) -> Dict[str, Any]:
        """
        Get memory usage statistics for the project state.

        Args:
            imported_modules: Dictionary of imported modules
            target_functions: Dictionary of target functions
            validation_results: List of validation results

        Returns:
            Dictionary with memory usage information
        """
        return {
            "imported_modules": len(imported_modules),
            "target_functions": sum(
                len(funcs) if isinstance(funcs, list) else 1
                for funcs in target_functions.values()
            ),
            "validation_results": len(validation_results),
            "module_usage_entries": len(self._module_usage),
            "max_results_limit": self._max_results,
            "cleanup_enabled": self._cleanup_enabled,
            "lazy_loading_enabled": self._lazy_loading_enabled,
            "most_used_modules": sorted(
                self._module_usage.items(), key=lambda x: x[1], reverse=True
            )[
                :10
            ],  # Top 10 most used modules
        }

    @property
    def cleanup_enabled(self) -> bool:
        """Check if cleanup is enabled."""
        return bool(self._cleanup_enabled)

    @property
    def lazy_loading_enabled(self) -> bool:
        """Check if lazy loading is enabled."""
        return bool(self._lazy_loading_enabled)

    @property
    def max_results(self) -> Optional[int]:
        """Get maximum results limit."""
        return self._max_results
