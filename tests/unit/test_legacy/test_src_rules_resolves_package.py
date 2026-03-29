from __future__ import annotations

from pathlib import Path

import src.rules


def test_src_rules_import_resolves_package_init():
    resolved = Path(src.rules.__file__).as_posix()
    assert resolved.endswith("src/rules/__init__.py")
