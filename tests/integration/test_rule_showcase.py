"""Integration tests for the per-rule showcase under ``example/rule_showcase``.

The showcase exists so every declaration marker has a worked example. These tests
keep that promise honest: a marker added without an example, or a showcase whose
declarations stop compiling, fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import pythonarchtesting.rules as rules
from pythonarchtesting.cli import main

SHOWCASE_CASES = (
    "api001_signature",
    "api002_method",
    "api003_attribute_ctor",
    "api004_factory",
    "api005_method_set",
    "api006_member_set",
    "dep001_imports",
    "enum001_enum",
    "flw001_flow",
    "mod001_modifiers",
    "neg001_absence",
    "nom001_inheritance",
    "pro001_protocol",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _showcase_root() -> Path:
    return _repo_root() / "example" / "rule_showcase"


def test_showcase_contains_exactly_the_expected_cases() -> None:
    present = {
        path.name
        for path in _showcase_root().iterdir()
        if (path / "reference").is_dir()
    }

    assert present == set(SHOWCASE_CASES)


@pytest.mark.parametrize("case_name", SHOWCASE_CASES)
def test_showcase_declarations_validate(case_name: str, monkeypatch, capsys) -> None:
    monkeypatch.chdir(_repo_root())
    reference = _showcase_root() / case_name / "reference"
    # Guard against a vacuous pass: the CLI exits 0 for a source path that does
    # not exist, so a missing showcase would otherwise look healthy.
    assert reference.is_dir()

    exit_code = main(
        ["--validate-declarations", "--source", str(reference), "--format", "json"]
    )
    capsys.readouterr()

    assert exit_code == 0


def test_every_public_marker_has_an_example() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (_repo_root() / "example").rglob("*.py")
    )

    missing = sorted(
        marker
        for marker in rules.__all__
        if not re.search(rf"\b{re.escape(marker)}\b", sources)
    )

    assert missing == []
