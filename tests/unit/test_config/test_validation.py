"""
Tests for configuration validation functionality.
"""

from dataclasses import replace

import pytest

from pythonarchtesting.config import (
    load_config,
    validate_configuration,
    validate_value,
)
from pythonarchtesting.config.data import create_config_from_dict
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
    "removed_section", ["arch_rules", "runtime", "structural_check", "type_check"]
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
        "[type_check]\nenabled = true\n",
    ],
)
def test_load_config_rejects_removed_sections(tmp_path, config_text: str) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Unknown configuration section"):
        load_config(config_path=str(config_path), cli_args={})


def test_load_config_rejects_removed_runtime_cli_args() -> None:
    with pytest.raises(
        ConfigurationError, match="Runtime options are no longer supported"
    ):
        load_config(cli_args={"runtime_fast": True})


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

    config = load_config(config_path=str(config_path), cli_args={})

    assert config.performance.default_timeout == 45
    for attr in (
        "parallel_processing",
        "max_workers",
        "min_parallel_items",
        "parallel_imports",
        "parallel_validation",
    ):
        assert not hasattr(config.performance, attr)


def test_load_config_autodiscovers_python_arch_testing_conf(
    tmp_path, monkeypatch
) -> None:
    config_path = tmp_path / "python_arch_testing.conf"
    config_path.write_text("[performance]\ndefault_timeout = 45\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.performance.default_timeout == 45


def test_load_config_uses_explicit_config_over_autodiscovery(
    tmp_path, monkeypatch
) -> None:
    autodiscovered = tmp_path / "python_arch_testing.conf"
    explicit = tmp_path / "explicit.conf"
    autodiscovered.write_text("[performance]\ndefault_timeout = 11\n", encoding="utf-8")
    explicit.write_text("[performance]\ndefault_timeout = 62\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    config = load_config(config_path=str(explicit))

    assert config.performance.default_timeout == 62


def test_load_config_falls_back_to_custom_config_conf_with_deprecation_warning(
    tmp_path, monkeypatch
) -> None:
    config_path = tmp_path / "custom_config.conf"
    config_path.write_text("[performance]\ndefault_timeout = 52\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    with pytest.deprecated_call(match="custom_config\\.conf"):
        config = load_config()

    assert config.performance.default_timeout == 52


def test_load_config_prefers_python_arch_testing_conf_when_both_exist(
    tmp_path, monkeypatch
) -> None:
    canonical = tmp_path / "python_arch_testing.conf"
    legacy = tmp_path / "custom_config.conf"
    canonical.write_text("[performance]\ndefault_timeout = 31\n", encoding="utf-8")
    legacy.write_text("[performance]\ndefault_timeout = 99\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    with pytest.deprecated_call(match="custom_config\\.conf"):
        config = load_config()

    assert config.performance.default_timeout == 31


def test_load_config_signature_no_longer_accepts_env() -> None:
    with pytest.raises(TypeError, match="env"):
        load_config(env={})  # type: ignore[call-arg]


def test_files_section_config_filename_keys_now_warn_as_unknown() -> None:
    result = validate_configuration(
        {
            "files": {
                "config_default": "defaults.conf",
                "config_custom": "custom_config.conf",
            }
        }
    )

    assert result.is_valid
    assert "files.config_default: Unknown configuration key" in result.warnings
    assert "files.config_custom: Unknown configuration key" in result.warnings


def test_load_config_no_longer_exposes_removed_type_check_section(tmp_path) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text("[import]\nmax_modules = 77\n", encoding="utf-8")

    config = load_config(config_path=str(config_path))

    assert config.import_config.max_modules == 77
    assert not hasattr(config, "type_check")


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
        assert "type_check" not in schema

        discovery_schema = get_schema_info("discovery")
        assert "max_discovery_depth" in discovery_schema

        with pytest.raises(ValueError):
            get_schema_info("unknown_section")


def test_build_report_snapshot_does_not_include_removed_type_check_section(tmp_path):
    from pythonarchtesting.report.api import build_report
    from pythonarchtesting.state import ProjectState, ValidationResult, ValidationStatus

    cfg = replace(
        create_config_from_dict({"report": {"include_config_snapshot": True}}),
        raw={},
    )
    state = ProjectState(target_path=str(tmp_path), reference_modules=[], config=cfg)
    state.add_validation_result(
        ValidationResult(
            status=ValidationStatus.OK,
            description="ok",
            check_type="alpha",
            src_function_name="a_func",
            src_package="pkg_a",
            src_line_num=1,
            src_file="a.py",
            target_function_name="a_ref",
            target_package="ref_a",
            details={},
        )
    )

    report = build_report(state, cfg)

    assert report["run"]["config_snapshot"] is not None
    assert "type_check" not in report["run"]["config_snapshot"]
