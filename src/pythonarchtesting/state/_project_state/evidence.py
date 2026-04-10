from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pythonarchtesting.evidence.collection import collect_static_evidence

if TYPE_CHECKING:  # pragma: no cover
    from ._typing import EvidenceStateLike


class ProjectStateEvidenceMixin:
    """Static analysis evidence collection."""

    def _collect_static_evidence(self: "EvidenceStateLike") -> dict[str, list[Any]]:
        if self._stores.evidence.static_evidence_cache is not None:
            return self._stores.evidence.static_evidence_cache

        if not self._context.target_project_path:
            evidence: dict[str, list[Any]] = {
                "import_edges": [],
                "call_sites": [],
                "modules": [],
            }
            self._stores.evidence.static_evidence_cache = evidence
            return evidence

        config = self._active_config()
        evidence = collect_static_evidence(
            root_path=Path(self._context.target_project_path),
            config=config,
            target_module_name=self._context.target_module_name,
        )
        self._stores.evidence.static_evidence_cache = evidence
        return evidence

    def _active_config(self: "EvidenceStateLike") -> Any:
        """Return active config, loading explicit defaults on first access."""
        return self._ensure_context_config().config
