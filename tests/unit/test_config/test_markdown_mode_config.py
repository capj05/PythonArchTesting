"""Tests for markdown_mode config field: defaulting, override, and rejection."""

from __future__ import annotations

import pytest

from pythonarchtesting.config import load_config, validate_configuration
from pythonarchtesting.exceptions import ConfigurationError


def test_default_config_has_standard_markdown_mode():
    config = load_config()
    assert config.report.markdown_mode == "standard"


def test_config_file_override_verbose(tmp_path):
    cfg_file = tmp_path / ".pythonarchtesting"
    cfg_file.write_text("[report]\nmarkdown_mode = verbose\n")
    config = load_config(config_path=str(cfg_file))
    assert config.report.markdown_mode == "verbose"


def test_config_file_override_debug(tmp_path):
    cfg_file = tmp_path / ".pythonarchtesting"
    cfg_file.write_text("[report]\nmarkdown_mode = debug\n")
    config = load_config(config_path=str(cfg_file))
    assert config.report.markdown_mode == "debug"


def test_config_file_invalid_value_rejected(tmp_path):
    cfg_file = tmp_path / ".pythonarchtesting"
    cfg_file.write_text("[report]\nmarkdown_mode = fancy\n")
    with pytest.raises(ConfigurationError):
        load_config(config_path=str(cfg_file))


def test_schema_validates_markdown_mode_allowed_values():
    result = validate_configuration({"report": {"markdown_mode": "verbose"}})
    assert result.is_valid


def test_schema_rejects_markdown_mode_unknown_value():
    result = validate_configuration({"report": {"markdown_mode": "pretty"}})
    assert not result.is_valid


def test_cli_args_markdown_mode_overrides_config(tmp_path):
    cfg_file = tmp_path / ".pythonarchtesting"
    cfg_file.write_text("[report]\nmarkdown_mode = verbose\n")
    config = load_config(
        config_path=str(cfg_file),
        cli_args={"markdown_mode": "debug"},
    )
    assert config.report.markdown_mode == "debug"


def test_cli_args_none_markdown_mode_does_not_override(tmp_path):
    cfg_file = tmp_path / ".pythonarchtesting"
    cfg_file.write_text("[report]\nmarkdown_mode = verbose\n")
    config = load_config(
        config_path=str(cfg_file),
        cli_args={"markdown_mode": None},
    )
    assert config.report.markdown_mode == "verbose"
