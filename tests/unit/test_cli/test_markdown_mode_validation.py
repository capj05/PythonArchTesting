"""Tests verifying CLI rejects --markdown-mode when combined with incompatible flags."""

from __future__ import annotations

import pytest

from pythonarchtesting.cli import main


def test_main_rejects_markdown_mode_with_json_format():
    with pytest.raises(SystemExit) as exc_info:
        main(["--target", "a", "--format", "json", "--markdown-mode", "verbose"])
    assert exc_info.value.code != 0


def test_main_rejects_markdown_mode_with_default_format():
    # default format is json, so --markdown-mode should still be rejected
    with pytest.raises(SystemExit) as exc_info:
        main(["--target", "a", "--markdown-mode", "verbose"])
    assert exc_info.value.code != 0
