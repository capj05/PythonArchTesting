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
        "exclude_hidden_dirs": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=True
        ),
        "follow_symlinks": ValidationRule(
            value_type=ValueType.BOOLEAN, default_value=False
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
            default_value="",
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
        "name_fallback": ValidationRule(
            value_type=ValueType.BOOLEAN,
            default_value=True,
        ),
        "include_nested_functions": ValidationRule(
            value_type=ValueType.BOOLEAN,
            default_value=False,
        ),
    },
}

__all__ = ["CONFIGURATION_SCHEMA"]
