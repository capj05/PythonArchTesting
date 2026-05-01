"""
Configuration data classes for the Python Architecture Testing toolkit.

This module contains pure data classes that represent configuration state
without any import-time side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True, slots=True)
class DiscoveryConfig:
    """Code discovery configuration."""

    max_discovery_depth: int = -1
    excluded_dirs: List[str] = field(
        default_factory=lambda: ["__pycache__", ".git", ".venv", "venv"]
    )
    included_file_patterns: List[str] = field(default_factory=lambda: ["*.py"])
    include_init_files: bool = True
    auto_discover: bool = True
    exclude_hidden_dirs: bool = True
    follow_symlinks: bool = False


@dataclass(frozen=True, slots=True)
class ReportingConfig:
    """Reporting configuration."""

    max_string_representation: int = 100
    error_detail_level: str = "full"
    include_traceback: bool = False
    output_formats: List[str] = field(default_factory=lambda: ["json"])


@dataclass(frozen=True, slots=True)
class FilesConfig:
    """File handling configuration."""

    python_extension: str = ".py"
    init_filename: str = "__init__.py"


@dataclass(frozen=True, slots=True)
class PerformanceConfig:
    """Performance tuning configuration."""

    default_timeout: int = 30


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    """Memory management configuration."""

    cleanup_enabled: bool = True
    lazy_loading: bool = True
    max_validation_results: int = 10000
    min_module_usage: int = 0
    max_module_age_hours: float = 24.0
    auto_cleanup: bool = True
    cleanup_interval: int = 1000


@dataclass(frozen=True, slots=True)
class ImportConfig:
    """Import handling configuration."""

    max_modules: int = 100
    import_timeout: float = 10.0
    show_import_warnings: bool = True


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Logging configuration."""

    level: str = "DEBUG"
    file: bool = True
    filename: str = "log.txt"
    output_file: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ReportConfig:
    """Report generation configuration."""

    schema_version: str = "2"
    validate_schema_v2: bool = False
    warnings_as_fail: bool = False
    include_config_snapshot: bool = False
    max_evidence_items_text: int = 3
    run_exit_policy: str = "any_fail"
    fail_threshold: int = 1
    markdown_detail: str = "verbose"


@dataclass(frozen=True, slots=True)
class ErrorHandlingConfig:
    """Error handling configuration."""

    continue_on_error: bool = True
    continue_on_import_error: bool = True
    show_detailed_errors: bool = True
    include_suggestions: bool = True
    max_error_context_depth: int = 5


@dataclass(frozen=True, slots=True)
class ProjectsConfig:
    """Project configuration."""

    source_path: Path
    targets: List[str] = field(default_factory=list)
    targets_dir: Optional[str] = None
    target_path: Optional[str] = None
    project_pattern: str = "*"
    exclude_patterns: List[str] = field(
        default_factory=lambda: [".git", "__pycache__", "template"]
    )
    required_modules: List[str] = field(
        default_factory=lambda: ["calculator", "data_processor"]
    )


@dataclass(frozen=True, slots=True)
class MatchingConfig:
    """Matching algorithm configuration."""

    threshold: float = 0.80
    delta: float = 0.03
    min_candidate: float = 0.50
    top_n: int = 5
    max_fuzzy_candidates: int = 5
    max_stage2_candidates: int = 0
    max_stage3_candidates: int = 0
    include_nested_functions: bool = False


@dataclass(frozen=True, slots=True)
class Config:
    """Main configuration data class containing all settings."""

    # Core configuration sections
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)
    files: FilesConfig = field(default_factory=FilesConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    import_config: ImportConfig = field(default_factory=ImportConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    error_handling: ErrorHandlingConfig = field(default_factory=ErrorHandlingConfig)
    projects: ProjectsConfig = field(
        default_factory=lambda: ProjectsConfig(source_path=Path("."))
    )
    matching: MatchingConfig = field(default_factory=MatchingConfig)

    # Raw configuration dictionary for advanced usage
    raw: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def _convert_value(value: Any, field_info: Any) -> Any:
    """Convert a value to target type, handling string inputs from ConfigParser."""
    if value is None:
        return None

    # Extract the actual type from field info
    import typing
    from dataclasses import Field

    if isinstance(field_info, Field):
        target_type = field_info.type
    else:
        target_type = field_info

    # Handle generic types like List[str]
    if hasattr(target_type, "__origin__"):
        origin = typing.get_origin(target_type)
        if origin is list:
            # Handle List[str] and similar
            if isinstance(value, str):
                return [item.strip() for item in value.split(",") if item.strip()]
            elif isinstance(value, list):
                return value
            else:
                return [str(value)]

    # If already the right type, return as-is
    try:
        if isinstance(target_type, type) and isinstance(value, target_type):
            return value
    except TypeError:
        # target_type might not be a real type (e.g., string representation)
        pass

    type_str = str(target_type).lower()
    if (
        isinstance(value, str)
        and value.strip().lower() == "null"
        and ("optional" in type_str or "nonetype" in type_str)
    ):
        return None

    # Handle string conversions from ConfigParser
    if isinstance(value, str):
        # Handle basic types by checking type names
        if "bool" in type_str:
            return value.lower() in ("true", "yes", "1", "on")
        elif "int" in type_str:
            return int(value)
        elif "float" in type_str:
            return float(value)
        elif "list" in type_str:
            # Handle comma-separated strings
            return [item.strip() for item in value.split(",") if item.strip()]
        elif "str" in type_str:
            return value
        elif "path" in type_str:
            from pathlib import Path

            return Path(value)

    # For lists, handle both string and list inputs
    if "list" in str(target_type).lower() and not isinstance(value, list):
        return [str(value)]

    return value


def create_config_from_dict(config_dict: Dict[str, Dict[str, Any]]) -> Config:
    """
    Create a Config instance from a raw configuration dictionary.

    Args:
        config_dict: Raw configuration dictionary

    Returns:
        Config instance with all sections populated
    """

    def _get_section(
        section_name: str, default_factory: Callable[..., Any], **kwargs: Any
    ) -> Any:
        # Use config_dict parameter from outer scope
        section_data = config_dict.get(section_name, {})
        if not section_data:
            return default_factory(**kwargs)

        dataclass_fields = getattr(default_factory, "__dataclass_fields__", {})
        fields = {f.name: f for f in dataclass_fields.values()}

        kwargs = {}
        for field_name, field_info in fields.items():
            if field_name in section_data:
                kwargs[field_name] = _convert_value(
                    section_data[field_name], field_info
                )

        return default_factory(**kwargs)

    return Config(
        discovery=_get_section("discovery", DiscoveryConfig),
        reporting=_get_section("reporting", ReportingConfig),
        files=_get_section("files", FilesConfig),
        performance=_get_section("performance", PerformanceConfig),
        memory=_get_section("memory", MemoryConfig),
        import_config=_get_section("import", ImportConfig),
        logging=_get_section("logging", LoggingConfig),
        report=_get_section("report", ReportConfig),
        error_handling=_get_section("error_handling", ErrorHandlingConfig),
        projects=_get_section("projects", ProjectsConfig, source_path=Path(".")),
        matching=_get_section("matching", MatchingConfig),
        raw=config_dict,
    )
