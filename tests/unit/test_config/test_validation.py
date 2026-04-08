"""
Tests for configuration validation functionality.
"""

import pytest

from pythonarchtesting.config import (
    load_config,
    validate_configuration,
    validate_value,
)
from pythonarchtesting.config.schema_rules import ValidationRule, ValueType
from pythonarchtesting.config.validator import get_schema_info
from pythonarchtesting.exceptions import ConfigurationError


def test_valid_config_structure(sample_config):
    result = validate_configuration(sample_config)
    assert result.is_valid
    assert not result.errors


def test_unknown_section_warning():
    result = validate_configuration({"unknown": {"foo": "bar"}})
    assert result.is_valid
    assert any(
        "Unknown configuration section" in warning for warning in result.warnings
    )


def test_invalid_value_rejected():
    config = {"discovery": {"max_discovery_depth": "invalid"}}
    result = validate_configuration(config)
    assert not result.is_valid
    assert any("max_discovery_depth" in error for error in result.errors)


def test_defaults_applied_for_missing_sections():
    result = validate_configuration({})
    assert result.is_valid
    assert "discovery.exclude_hidden_dirs" in result.applied_defaults


@pytest.mark.parametrize(
    "removed_section", ["arch_rules", "runtime", "structural_check"]
)
def test_removed_sections_now_fail_validation(removed_section: str) -> None:
    result = validate_configuration({removed_section: {"enabled": True}})
    assert not result.is_valid
    assert f"Unknown configuration section: {removed_section}" in result.errors


@pytest.mark.parametrize(
    "config_text",
    [
        "[arch_rules]\nenabled = true\n",
        "[runtime]\nmode = static-only\n",
        "[structural_check]\nenabled = true\n",
    ],
)
def test_load_config_rejects_removed_sections(tmp_path, config_text: str) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Unknown configuration section"):
        load_config(config_path=str(config_path), env={}, cli_args={})


def test_load_config_rejects_removed_runtime_cli_args() -> None:
    with pytest.raises(
        ConfigurationError, match="Runtime options are no longer supported"
    ):
        load_config(
            env={},
            cli_args={"runtime_fast": True},
        )


def test_parallel_performance_keys_now_warn_as_unknown() -> None:
    result = validate_configuration(
        {
            "performance": {
                "parallel_processing": True,
                "max_workers": 4,
                "min_parallel_items": 2,
                "parallel_imports": True,
                "parallel_validation": True,
            }
        }
    )
    assert result.is_valid
    for key in (
        "parallel_processing",
        "max_workers",
        "min_parallel_items",
        "parallel_imports",
        "parallel_validation",
    ):
        assert any(
            f"performance.{key}: Unknown configuration key" in warning
            for warning in result.warnings
        )


def test_load_config_no_longer_exposes_parallel_performance_fields(tmp_path) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text("[performance]\ndefault_timeout = 45\n", encoding="utf-8")

    config = load_config(config_path=str(config_path), env={}, cli_args={})

    assert config.performance.default_timeout == 45
    for attr in (
        "parallel_processing",
        "max_workers",
        "min_parallel_items",
        "parallel_imports",
        "parallel_validation",
    ):
        assert not hasattr(config.performance, attr)


class TestValidationRule:
    """Test individual validation rules."""

    def test_integer_validation(self):
        rule = ValidationRule(
            value_type=ValueType.INTEGER,
            min_value=1,
            max_value=100,
            default_value=50,
        )

        is_valid, error = rule.validate(50, "test", "key")
        assert is_valid, f"Valid integer should pass: {error}"

        is_valid, _ = rule.validate(0, "test", "key")
        assert not is_valid

        is_valid, _ = rule.validate(150, "test", "key")
        assert not is_valid

        is_valid, _ = rule.validate("75", "test", "key")
        assert is_valid

    def test_boolean_validation(self):
        rule = ValidationRule(value_type=ValueType.BOOLEAN, default_value=True)

        is_valid, error = rule.validate(True, "test", "key")
        assert is_valid, f"Valid boolean should pass: {error}"

        is_valid, _ = rule.validate(False, "test", "key")
        assert is_valid

        is_valid, _ = rule.validate("true", "test", "key")
        assert is_valid

        is_valid, _ = rule.validate("false", "test", "key")
        assert is_valid

        is_valid, _ = rule.validate("yes", "test", "key")
        assert is_valid

        is_valid, _ = rule.validate("no", "test", "key")
        assert is_valid

    def test_string_validation(self):
        rule = ValidationRule(
            value_type=ValueType.STRING,
            min_length=3,
            max_length=10,
            pattern=r"^[a-zA-Z]+$",
            default_value="test",
        )

        is_valid, error = rule.validate("hello", "test", "key")
        assert is_valid, f"Valid string should pass: {error}"

        is_valid, _ = rule.validate("ab", "test", "key")
        assert not is_valid

        is_valid, _ = rule.validate("toolongstring", "test", "key")
        assert not is_valid

        is_valid, _ = rule.validate("test123", "test", "key")
        assert not is_valid

    def test_list_validation(self):
        rule = ValidationRule(
            value_type=ValueType.LIST, default_value=["item1", "item2"]
        )

        is_valid, error = rule.validate(["item1", "item2"], "test", "key")
        assert is_valid, f"Valid list should pass: {error}"

        is_valid, error = rule.validate("item1, item2", "test", "key")
        assert is_valid, f"String list should convert: {error}"


class TestConfigurationValidator:
    """Test configuration validator."""

    def test_validate_configuration(self):
        config_dict = {
            "discovery": {
                "max_discovery_depth": 5,
                "invalid_key": "invalid_value",
            },
            "import": {"max_modules": 50, "show_import_warnings": "invalid_boolean"},
            "unknown_section": {"unknown_key": "value"},
        }

        result = validate_configuration(config_dict)

        assert not result.is_valid
        assert len(result.errors) > 0
        assert len(result.warnings) > 0
        assert len(result.applied_defaults) > 0

    def test_validate_value(self):
        is_valid, error = validate_value("discovery", "max_discovery_depth", 1000)
        assert is_valid, f"Valid value should pass: {error}"

        is_valid, error = validate_value("import", "max_modules", -1)
        assert not is_valid
        assert "not in range" in error

        is_valid, _ = validate_value("unknown_section", "unknown_key", "value")
        assert not is_valid

    def test_get_schema_info(self):
        schema = get_schema_info()
        assert "discovery" in schema
        assert "import" in schema

        discovery_schema = get_schema_info("discovery")
        assert "max_discovery_depth" in discovery_schema

        with pytest.raises(ValueError):
            get_schema_info("unknown_section")
