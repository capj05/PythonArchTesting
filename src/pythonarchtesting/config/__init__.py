"""
Public configuration API.
"""

from .data import Config
from .loader import load_config
from .projects import ProjectsConfig, TargetSpec, resolve_projects_config
from .validator import validate_configuration, validate_value

__all__ = [
    "Config",
    "load_config",
    "ProjectsConfig",
    "TargetSpec",
    "resolve_projects_config",
    "validate_configuration",
    "validate_value",
]
