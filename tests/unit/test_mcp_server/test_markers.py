from __future__ import annotations

import site
import sys
from pathlib import Path

import pytest

import pythonarchtesting.rules as rules
from pythonarchtesting.mcp_server import markers as markers_module
from pythonarchtesting.mcp_server.errors import ToolInputError, require_absolute
from pythonarchtesting.mcp_server.markers import describe_marker, list_markers

PYPROJECT = Path(__file__).parents[3] / "pyproject.toml"


def test_every_exported_marker_has_a_doc_and_vice_versa():
    assert {m["name"] for m in list_markers()} == set(rules.__all__)


def test_list_markers_fields():
    by_name = {m["name"]: m for m in list_markers()}
    runtime = by_name["forbid_runtime_calls"]
    assert runtime["category"] == "Runtime structure"
    assert runtime["requires_dynamic"] is True
    static = by_name["is_enum"]
    assert static["requires_dynamic"] is False
    assert static["summary"].startswith("Require the matched target class")


def test_list_markers_filters_by_category():
    items = list_markers("runtime STRUCTURE")
    assert items
    assert all(m["category"] == "Runtime structure" for m in items)


def test_list_markers_unknown_category_lists_known():
    with pytest.raises(ToolInputError, match="Runtime structure"):
        list_markers("nope")


def test_describe_marker_returns_full_markdown():
    assert "## Arguments" in describe_marker("forbid_runtime_calls")["markdown"]


def test_describe_unknown_marker_suggests():
    with pytest.raises(ToolInputError, match="forbid_runtime_calls"):
        describe_marker("forbid_runtime_call")


def test_require_absolute_rejects_relative():
    with pytest.raises(ToolInputError, match="must be an absolute path"):
        require_absolute("rel/dir", "reference")
    assert require_absolute("/tmp", "reference") == Path("/tmp")


def test_pyproject_ships_marker_docs():
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        tomllib = pytest.importorskip("tomli")
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    data_files = data["tool"]["setuptools"]["data-files"]
    assert data_files["share/pythonarchtesting/markers"] == ["docs/markers/*.md"]
    assert (
        data["project"]["scripts"]["python-arch-test-mcp"]
        == "pythonarchtesting.mcp_server.server:main"
    )


def test_marker_docs_dir_falls_back_to_user_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    user_base = tmp_path / "userbase"
    docs = user_base / "share" / "pythonarchtesting" / "markers"
    docs.mkdir(parents=True)
    monkeypatch.setattr(
        markers_module, "__file__", str(tmp_path / "a" / "b" / "c" / "d.py")
    )
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "prefix"))
    monkeypatch.setattr(site, "getuserbase", lambda: str(user_base))
    assert markers_module.marker_docs_dir() == docs
