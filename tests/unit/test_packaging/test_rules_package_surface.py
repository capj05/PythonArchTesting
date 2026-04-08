from __future__ import annotations

from pathlib import Path

import pythonarchtesting.rules


def test_pythonarchtesting_rules_import_resolves_package_init():
    resolved = Path(pythonarchtesting.rules.__file__).as_posix()
    assert resolved.endswith("src/pythonarchtesting/rules/__init__.py")
