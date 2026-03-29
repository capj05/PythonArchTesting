"""
Configuration loader for the Python Architecture Testing toolkit.

This module provides explicit configuration loading without import-time side effects.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.constants import FileConstants
from src.exceptions import ConfigurationError, ErrorContext

from .data import Config, create_config_from_dict
from .validator import validate_configuration


def _serialize_config_value(value: Any) -> str:
    """Convert a configuration value to string for ConfigParser."""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _package_root() -> Path:
    """Get the package root directory."""
    return Path(__file__).resolve().parents[2]


def _default_config_path() -> str:
    """Get the default configuration file path."""
    return str(_package_root() / FileConstants.DEFAULT_CONFIG_FILE)


def _load_config_file(config_path: str) -> Dict[str, Dict[str, str]]:
    """
    Load configuration from a file.

    Args:
        config_path: Path to configuration file

    Returns:
        Raw configuration dictionary

    Raises:
        ConfigurationError: If file cannot be loaded
    """
    config = configparser.ConfigParser(interpolation=configparser.BasicInterpolation())

    try:
        config_path = os.path.abspath(config_path)
        files_read = config.read(config_path)

        if not files_read:
            raise ConfigurationError(
                f"Configuration file not found or unreadable: {config_path}",
                context=ErrorContext(file=config_path),
                error_code="CONFIG_FILE_NOT_FOUND",
                suggestion="Check file path and permissions",
            )

        # Convert to regular dict
        result = {}
        for section in config.sections():
            result[section] = dict(config[section])

        return result

    except ConfigurationError:
        raise
    except Exception as e:
        raise ConfigurationError(
            f"Error loading configuration from {config_path}: {str(e)}",
            context=ErrorContext(file=config_path),
            original_error=e,
            error_code="CONFIG_LOAD_ERROR",
        )


def _convert_types_in_config_dict(
    config_dict: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Convert string values from ConfigParser to appropriate types before validation."""
    from .schema_data import CONFIGURATION_SCHEMA

    converted_dict = {}

    for section_name, section_data in config_dict.items():
        converted_section = {}

        # Get schema for this section if available
        section_schema = CONFIGURATION_SCHEMA.get(section_name, {})

        for key_name, value in section_data.items():
            if key_name in section_schema:
                rule = section_schema[key_name]
                converted_value = _convert_value_by_rule(value, rule)
                converted_section[key_name] = converted_value
            else:
                converted_section[key_name] = value

        converted_dict[section_name] = converted_section

    return converted_dict


def _convert_value_by_rule(value: Any, rule: Any) -> Any:
    """Convert a value based on validation rule type."""
    if value is None:
        return None

    # If already the right type, return as-is
    if rule.value_type.value == "boolean":
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "on")
        else:
            return bool(value)
    elif rule.value_type.value == "integer":
        if isinstance(value, int):
            return value
        elif isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                # Let validation handle the error
                return value
        else:
            try:
                return int(value)
            except (ValueError, TypeError):
                return value
    elif rule.value_type.value == "float":
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            return float(value)
        else:
            return float(value)
    elif rule.value_type.value == "list":
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        else:
            return [str(value)]
    else:
        # For string and other types, return as-is
        return value


def _apply_defaults_and_validate(
    config_dict: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Apply defaults and validate configuration.

    Args:
        config_dict: Raw configuration dictionary

    Returns:
        Validated configuration dictionary with defaults applied

    Raises:
        ConfigurationError: If validation fails
    """
    # Convert types before validation
    converted_config = _convert_types_in_config_dict(config_dict)

    validation_result = validate_configuration(converted_config)

    if not validation_result.is_valid:
        error_message = "Configuration validation failed:\n" + "\n".join(
            validation_result.errors
        )
        raise ConfigurationError(
            error_message,
            error_code="CONFIG_VALIDATION_FAILED",
        )

    # Log warnings
    for warning in validation_result.warnings:
        print(f"Configuration warning: {warning}")

    # Apply defaults
    result = {section: dict(items) for section, items in config_dict.items()}

    for key_path, default_value in validation_result.applied_defaults.items():
        section, key = key_path.split(".", 1)
        if section not in result:
            result[section] = {}
        result[section][key] = _serialize_config_value(default_value)

    return result


def _normalize_logging_section(config_dict: Dict[str, Dict[str, Any]]) -> None:
    """Normalize logging configuration keys and aliases."""
    if "logging" not in config_dict:
        config_dict["logging"] = {}

    log_section = config_dict["logging"]
    filename = (log_section.get("filename") or "").strip() or None
    alias = (log_section.get("output_file") or "").strip() or None

    if filename and not isinstance(filename, str):
        raise ConfigurationError("logging.filename must be a string")
    if alias and not isinstance(alias, str):
        raise ConfigurationError("logging.output_file must be a string")

    # Alias precedence with default override
    if alias and (not filename or filename == "log.txt"):
        log_section["filename"] = alias
    elif filename:
        log_section["filename"] = filename


def _normalize_report_section(config_dict: Dict[str, Dict[str, Any]]) -> None:
    """Normalize report configuration (schema_version)."""
    if "report" not in config_dict:
        config_dict["report"] = {}

    report_section = config_dict["report"]
    schema_version = str(report_section.get("schema_version") or "2").strip()
    if schema_version != "2":
        print(f"Configuration warning: Invalid report.schema_version={
            schema_version!r}; " "falling back to '2'")
        schema_version = "2"
    report_section["schema_version"] = schema_version


def _reject_removed_runtime_cli_args(cli_args: Dict[str, Any]) -> None:
    removed_flags = {
        "runtime_max_probe_modules": "--runtime-max-probe-modules",
        "runtime_fast": "--runtime-fast",
        "runtime_allow_unsafe_probes": "--allow-unsafe-probes",
        "runtime_isolation": "--runtime-isolation",
    }
    used = []
    for key, flag in removed_flags.items():
        value = cli_args.get(key)
        if value not in (None, False):
            used.append(flag)
    if used:
        joined = ", ".join(sorted(used))
        raise ConfigurationError(
            "Runtime options are no longer supported in static-only mode: "
            f"{joined}. Remove these flags and use static analysis inputs only.",
            error_code="CONFIG_RUNTIME_FLAGS_REMOVED",
        )


def load_config(
    *,
    config_path: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    cli_args: Optional[Dict[str, Any]] = None,
) -> Config:
    """
    Load configuration from files, environment, and CLI arguments.

    This function performs explicit configuration loading without any
    import-time side effects. It can be called multiple times with
    different parameters.

    Args:
        config_path: Optional path to custom configuration file
        env: Optional environment mapping (defaults to os.environ)
        cli_args: Optional CLI arguments dictionary

    Returns:
        Fully validated Config object

    Raises:
        ConfigurationError: If configuration is invalid or cannot be loaded
    """
    env = env or os.environ
    cli_args = cli_args or {}
    _reject_removed_runtime_cli_args(cli_args)

    # Start with empty configuration
    config_dict: Dict[str, Dict[str, Any]] = {}

    # Load default configuration
    default_config_path = _default_config_path()
    if os.path.exists(default_config_path):
        default_config = _load_config_file(default_config_path)
        _merge_config_dicts(config_dict, default_config)
    else:
        print(f"Warning: Default configuration file '{default_config_path}' not found")

    # Load custom configuration
    if config_path:
        if not os.path.exists(config_path):
            raise ConfigurationError(
                f"Provided configuration file not found: {config_path}",
                error_code="CONFIG_FILE_NOT_FOUND",
            )
        custom_config = _load_config_file(config_path)
        _merge_config_dicts(config_dict, custom_config)
    else:
        # Try to load custom config from current directory
        custom_config_filename = "python_arch_testing.conf"
        custom_config_path = os.path.join(os.getcwd(), custom_config_filename)
        if os.path.exists(custom_config_path):
            custom_config = _load_config_file(custom_config_path)
            _merge_config_dicts(config_dict, custom_config)

    # Apply CLI arguments (highest priority)
    if cli_args:
        _apply_cli_args(config_dict, cli_args)

    # Apply defaults and validate
    validated_config = _apply_defaults_and_validate(config_dict)

    # Normalize special sections
    _normalize_logging_section(validated_config)
    _normalize_report_section(validated_config)

    # Create Config object
    return create_config_from_dict(validated_config)


def _merge_config_dicts(
    base: Dict[str, Dict[str, Any]], overlay: Dict[str, Dict[str, Any]]
) -> None:
    """
    Merge overlay configuration into base configuration.

    Args:
        base: Base configuration dictionary (modified in-place)
        overlay: Overlay configuration to merge
    """
    for section_name, section_data in overlay.items():
        if section_name not in base:
            base[section_name] = {}
        base[section_name].update(section_data)


def _apply_cli_args(
    config_dict: Dict[str, Dict[str, Any]], cli_args: Dict[str, Any]
) -> None:
    """
    Apply CLI arguments to configuration dictionary.

    Args:
        config_dict: Configuration dictionary (modified in-place)
        cli_args: CLI arguments dictionary
    """
    # Map common CLI arguments to configuration keys
    cli_mapping = {
        "verbose": ("logging", "level", "DEBUG"),
        "quiet": ("logging", "level", "ERROR"),
        "timeout": ("performance", "default_timeout"),
        "output_format": ("reporting", "output_formats"),
    }

    for cli_key, value in cli_args.items():
        if cli_key in cli_mapping and value is not None:
            mapping = cli_mapping[cli_key]
            if len(mapping) == 3:
                section, key, transform = mapping
                # Only apply verbose/quiet flags when they are True
                if cli_key in ["verbose", "quiet"] and not value:
                    continue
                if transform == "DEBUG" and value:
                    value = "DEBUG"
                elif transform == "ERROR" and value:
                    value = "ERROR"
                elif cli_key == "runtime_fast" and not value:
                    continue
            else:
                section, key = mapping

            if section not in config_dict:
                config_dict[section] = {}
            config_dict[section][key] = _serialize_config_value(value)
