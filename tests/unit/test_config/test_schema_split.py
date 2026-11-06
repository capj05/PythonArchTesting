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


def test_sections_without_a_live_key_are_not_in_schema() -> None:
    for section in ("files", "performance", "import", "reporting", "error_handling"):
        assert section not in CONFIGURATION_SCHEMA
