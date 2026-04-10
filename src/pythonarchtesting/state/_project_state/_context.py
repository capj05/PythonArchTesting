from __future__ import annotations

from dataclasses import dataclass

from pythonarchtesting.config import Config


@dataclass(frozen=True)
class ProjectContext:
    config: Config | None
    target_project_path: str | None
    reference_modules: list[str]
    validation_scope: str
    target_module_name: str | None
