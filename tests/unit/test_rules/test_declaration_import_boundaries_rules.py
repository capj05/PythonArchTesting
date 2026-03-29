from __future__ import annotations

import json
import subprocess
import sys

import pytest

DECLARATION_MODULES = ("src.rules.declaration.core",)


@pytest.mark.parametrize("module_name", DECLARATION_MODULES)
def test_declaration_module_import_does_not_pull_execution_or_reporting(
    module_name: str,
) -> None:
    code = f"""
import importlib
import json
import sys

forbidden_prefixes = ("src.execution", "src.report", "sqlalchemy")
before = set(sys.modules)
importlib.import_module("{module_name}")
after = set(sys.modules)

delta_forbidden = sorted(
    name for name in (after - before) if name.startswith(forbidden_prefixes)
)
print(json.dumps({{"delta_forbidden": delta_forbidden}}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["delta_forbidden"] == []


def test_supported_rules_remain_declaration_only() -> None:
    code = """
import json
import sys
from typing import Annotated
import src.rules as rules

forbidden_prefixes = ("src.execution", "src.report", "sqlalchemy")
before = set(sys.modules)

def marker(value: int) -> int:
    __archtest__: Annotated[None, rules.required_entity_signature]  # noqa: F842
    return value

after = set(sys.modules)
delta_forbidden = sorted(
    name for name in (after - before) if name.startswith(forbidden_prefixes)
)
print(
    json.dumps(
        {
            "delta_forbidden": delta_forbidden,
            "has_rule_specs": hasattr(marker, "__dict__"),
        }
    )
)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["delta_forbidden"] == []
