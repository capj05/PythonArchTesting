from __future__ import annotations

from pythonarchtesting.config.accessors import (
    get_bool,
    get_float,
    get_int,
    get_section,
)
from pythonarchtesting.config.data import create_config_from_dict


def _typed_config():
    return create_config_from_dict(
        {
            "discovery": {"max_discovery_depth": "7"},
            "matching": {"threshold": "0.91"},
            "report": {"include_config_snapshot": "true"},
        }
    )


def test_accessors_return_expected_values_for_typed_config():
    typed = _typed_config()

    assert get_int(typed, "discovery", "max_discovery_depth", 0) == 7
    assert get_float(typed, "matching", "threshold", 0.0) == 0.91
    assert get_bool(typed, "report", "include_config_snapshot", False) is True


def test_get_section_supports_typed_config_and_mapping():
    typed = _typed_config()
    section = get_section(typed, "discovery")
    assert section["max_discovery_depth"] == 7

    mapping = {"discovery": {"max_discovery_depth": "3"}}
    assert get_int(mapping, "discovery", "max_discovery_depth", 0) == 3
