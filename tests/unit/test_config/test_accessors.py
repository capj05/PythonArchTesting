from __future__ import annotations

from src.config.accessors import (
    get_bool,
    get_float,
    get_int,
    get_section,
)
from src.config.data import create_config_from_dict


def _typed_config():
    return create_config_from_dict(
        {
            "import": {"max_modules": "7", "import_timeout": "9.5"},
            "matching": {"threshold": "0.91"},
            "report": {"include_config_snapshot": "true"},
        }
    )


def test_accessors_return_expected_values_for_typed_config():
    typed = _typed_config()

    assert get_int(typed, "import", "max_modules", 0) == 7
    assert get_float(typed, "import", "import_timeout", 0.0) == 9.5
    assert get_bool(typed, "report", "include_config_snapshot", False) is True


def test_get_section_supports_mapping_and_import_section_alias():
    typed = _typed_config()
    section = get_section(typed, "import")
    assert section["max_modules"] == 7

    mapping = {"import": {"max_modules": "3"}}
    assert get_int(mapping, "import", "max_modules", 0) == 3
