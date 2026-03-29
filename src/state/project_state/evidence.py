from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.config import load_config
from src.evidence.collection import collect_static_evidence
from src.state.discovery import ModuleDiscovery
from src.state.memory_manager import MemoryManager

if TYPE_CHECKING:  # pragma: no cover
    from ._typing import ProjectStateLike


class ProjectStateEvidenceMixin:
    """Static analysis evidence collection."""

    config: Any
    target_project_path: str | None
    target_module_name: str | None
    _static_evidence_cache: dict[str, list[Any]] | None
    memory_manager: MemoryManager
    module_discovery: ModuleDiscovery

    def _collect_static_evidence(self: "ProjectStateLike") -> dict[str, list[Any]]:
        if self._static_evidence_cache is not None:
            return self._static_evidence_cache

        if not self.target_project_path:
            evidence: dict[str, list[Any]] = {
                "import_edges": [],
                "call_sites": [],
                "modules": [],
            }
            self._static_evidence_cache = evidence
            return evidence

        evidence = collect_static_evidence(
            root_path=Path(self.target_project_path),
            config=self._active_config(),
            target_module_name=self.target_module_name,
        )
        self._static_evidence_cache = evidence
        return evidence

    def _active_config(self: "ProjectStateLike") -> Any:
        """Return active config, loading explicit defaults on first access."""
        if self.config is None:
            self.config = load_config()
            self.memory_manager = MemoryManager(config=self.config)
            self.module_discovery.set_config(self.config)
        return self.config
