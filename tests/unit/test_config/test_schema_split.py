from __future__ import annotations

from pythonarchtesting.config.schema_data import (
    CONFIGURATION_SCHEMA as CONFIGURATION_SCHEMA_DATA,
)
from pythonarchtesting.config.schema_rules import ValidationRule as ValidationRuleRules
from pythonarchtesting.config.schema_rules import ValueType as ValueTypeRules

CONFIGURATION_SCHEMA = CONFIGURATION_SCHEMA_DATA
ValidationRule = ValidationRuleRules
ValueType = ValueTypeRules


def test_split_schema_modules_define_expected_symbols() -> None:
    assert CONFIGURATION_SCHEMA is CONFIGURATION_SCHEMA_DATA
    assert ValidationRule is ValidationRuleRules
    assert ValueType is ValueTypeRules


def test_schema_payload_still_contains_expected_sections() -> None:
    assert "runtime" not in CONFIGURATION_SCHEMA
    assert "arch_rules" not in CONFIGURATION_SCHEMA
    assert "structural_check" not in CONFIGURATION_SCHEMA
    assert "type_check" not in CONFIGURATION_SCHEMA


def test_files_schema_does_not_include_bootstrap_filename_keys() -> None:
    files_schema = CONFIGURATION_SCHEMA["files"]
    assert "config_default" not in files_schema
    assert "config_custom" not in files_schema


def test_parallel_performance_keys_are_not_in_schema() -> None:
    performance_schema = CONFIGURATION_SCHEMA["performance"]
    for key in (
        "parallel_processing",
        "max_workers",
        "min_parallel_items",
        "parallel_imports",
        "parallel_validation",
    ):
        assert key not in performance_schema
