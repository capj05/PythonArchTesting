"""Configuration schema payload definitions."""

from __future__ import annotations

from typing import Dict

from .schema_rules import ValidationRule, ValueType

# Configuration schema definition
CONFIGURATION_SCHEMA: Dict[str, Dict[str, ValidationRule]] = {
    "discovery": {
        "max_discovery_depth": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=-1,
            default_value=-1,
            error_message="Discovery depth must be -1 (unlimited) or positive",
        ),
        "excluded_dirs": ValidationRule(
            value_type=ValueType.LIST,
            default_value=["__pycache__", ".git", ".venv", "venv"],
        ),
        "included_file_patterns": ValidationRule(
            value_type=ValueType.LIST,
            allowed_values=["*.py", "*.pyx", "*.pyi"],
            default_value=["*.py"],
        ),
        "include_init_files": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
        "auto_discover": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
        "exclude_hidden_dirs": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
        "follow_symlinks": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=False
        ),
    },
    "reporting": {
        "max_string_representation": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=10,
            max_value=1000,
            default_value=100,
        ),
        "error_detail_level": ValidationRule(
            value_type=ValueType.STRING,
            allowed_values=["minimal", "standard", "full"],
            default_value="full",
        ),
        "include_traceback": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=False
        ),
        "output_formats": ValidationRule(
            value_type=ValueType.LIST,
            default_value=["json"],
            allowed_values=["json", "markdown"],
            error_message="Output formats must be valid format names",
        ),
    },
    "files": {
        "python_extension": ValidationRule(
            value_type=ValueType.STRING, pattern=r"^\.[a-zA-Z]+$", default_value=".py"
        ),
        "init_filename": ValidationRule(
            value_type=ValueType.STRING,
            pattern=r"^[a-zA-Z_][a-zA-Z0-9_.]*\.py$",
            default_value="__init__.py",
        ),
    },
    "performance": {
        "default_timeout": ValidationRule(
            value_type=ValueType.INTEGER, min_value=1, max_value=3600, default_value=30
        ),
    },
    "memory": {
        "cleanup_enabled": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
        "lazy_loading": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
        "max_validation_results": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=100,
            max_value=100000,
            default_value=10000,
            error_message="Max validation results must be between 100 and 100000",
        ),
        "min_module_usage": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=0,
            max_value=1000,
            default_value=0,
            error_message="Min module usage must be between 0 and 1000",
        ),
        "max_module_age_hours": ValidationRule(
            value_type=ValueType.FLOAT,
            min_value=0.1,
            max_value=168.0,  # 1 week
            default_value=24.0,
            error_message="Max module age must be between 0.1 and 168 hours",
        ),
        "auto_cleanup": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
        "cleanup_interval": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=10,
            max_value=10000,
            default_value=1000,
            error_message="Cleanup interval must be between 10 and 10000",
        ),
    },
    "import": {
        "max_modules": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=1,
            max_value=10000,
            default_value=100,
            error_message="Max modules must be between 1 and 10000",
        ),
        "import_timeout": ValidationRule(
            value_type=ValueType.FLOAT,
            min_value=0.1,
            max_value=300.0,
            default_value=10.0,
        ),
        "show_import_warnings": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
    },
    "logging": {
        "level": ValidationRule(
            value_type=ValueType.STRING,
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default_value="DEBUG",
        ),
        "file": ValidationRule(value_type=ValueType.BOOLEAN, default_value=True),
        "filename": ValidationRule(
            value_type=ValueType.STRING,
            pattern=r"^[a-zA-Z0-9._-]+$",
            default_value="log.txt",
        ),
        "output_file": ValidationRule(
            value_type=ValueType.STRING,
            pattern=r"^[a-zA-Z0-9._-]+$",
            default_value=None,
        ),
    },
    "report": {
        "schema_version": ValidationRule(
            value_type=ValueType.STRING,
            default_value="2",
        ),
        "validate_schema_v2": ValidationRule(
            value_type=ValueType.BOOLEAN,
            default_value=False,
        ),
        "warnings_as_fail": ValidationRule(
            value_type=ValueType.BOOLEAN,
            default_value=False,
        ),
        "include_config_snapshot": ValidationRule(
            value_type=ValueType.BOOLEAN,
            default_value=False,
        ),
        "max_evidence_items_text": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=0,
            max_value=1000,
            default_value=3,
        ),
        "run_exit_policy": ValidationRule(
            value_type=ValueType.STRING,
            allowed_values=["any_fail", "all_fail", "threshold"],
            default_value="any_fail",
        ),
        "fail_threshold": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=1,
            max_value=100000,
            default_value=1,
        ),
        "markdown_detail": ValidationRule(
            value_type=ValueType.STRING,
            allowed_values=["summary", "verbose", "debug"],
            default_value="verbose",
        ),
    },
    "error_handling": {
        "continue_on_error": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
        "continue_on_import_error": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
        "show_detailed_errors": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
        "include_suggestions": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
        "max_error_context_depth": ValidationRule(
            value_type=ValueType.INTEGER, min_value=1, max_value=20, default_value=5
        ),
    },
    "projects": {
        "source_path": ValidationRule(
            value_type=ValueType.PATH,
            default_value=".",
            error_message="Source path must be a valid directory path",
        ),
        "targets": ValidationRule(
            value_type=ValueType.LIST,
            default_value=[],
            error_message="Targets must be a list of paths",
        ),
        "targets_dir": ValidationRule(
            value_type=ValueType.PATH,
            default_value="",
            error_message="Targets directory must be a valid directory path",
        ),
        "target_path": ValidationRule(
            value_type=ValueType.PATH,
            default_value="./target",
            error_message="Target path must be a valid directory path",
        ),
        "project_pattern": ValidationRule(
            value_type=ValueType.STRING,
            pattern=r"^[\w\-. *]+$",
            default_value="*",
            error_message="Project pattern must be a valid glob pattern",
        ),
        "exclude_patterns": ValidationRule(
            value_type=ValueType.LIST,
            default_value=[".git", "__pycache__", "template"],
            error_message="Exclude patterns must be a list of strings",
        ),
        "required_modules": ValidationRule(
            value_type=ValueType.LIST,
            default_value=["calculator", "data_processor"],
            error_message="Required modules must be a list of strings",
        ),
    },
    "matching": {
        "threshold": ValidationRule(
            value_type=ValueType.FLOAT,
            min_value=0.0,
            max_value=1.0,
            default_value=0.80,
        ),
        "delta": ValidationRule(
            value_type=ValueType.FLOAT,
            min_value=0.0,
            max_value=1.0,
            default_value=0.03,
        ),
        "min_candidate": ValidationRule(
            value_type=ValueType.FLOAT,
            min_value=0.0,
            max_value=1.0,
            default_value=0.50,
        ),
        "top_n": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=1,
            max_value=100,
            default_value=5,
        ),
        "max_fuzzy_candidates": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=1,
            max_value=100,
            default_value=5,
        ),
        "max_stage2_candidates": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=0,
            max_value=100000,
            default_value=0,
        ),
        "max_stage3_candidates": ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=0,
            max_value=100000,
            default_value=0,
        ),
        "include_nested_functions": ValidationRule(
            value_type=ValueType.BOOLEAN,
            default_value=False,
        ),
    },
}

__all__ = ["CONFIGURATION_SCHEMA"]
