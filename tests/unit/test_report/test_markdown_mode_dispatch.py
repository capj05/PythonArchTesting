"""Tests verifying markdown_mode is forwarded through the reporting dispatch chain."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

import pythonarchtesting.report.api as api
import pythonarchtesting.report.lazy as lazy


# ---------------------------------------------------------------------------
# resolve_markdown_mode helper
# ---------------------------------------------------------------------------


def test_resolve_mode_explicit_wins():
    cfg = SimpleNamespace(report=SimpleNamespace(markdown_mode="verbose"))
    assert api.resolve_markdown_mode(cfg, "debug") == "debug"


def test_resolve_mode_from_config():
    cfg = SimpleNamespace(report=SimpleNamespace(markdown_mode="verbose"))
    assert api.resolve_markdown_mode(cfg) == "verbose"


def test_resolve_mode_default_when_no_config():
    assert api.resolve_markdown_mode(None) == "standard"


def test_resolve_mode_default_when_config_missing_attr():
    assert api.resolve_markdown_mode(object()) == "standard"


# ---------------------------------------------------------------------------
# JSON generation ignores markdown_mode
# ---------------------------------------------------------------------------


def test_generate_single_target_json_does_not_pass_mode(monkeypatch):
    render_json_calls: list[dict[str, Any]] = []

    def fake_render_json(document: Any) -> str:
        render_json_calls.append({"document": document})
        return '{"ok": true}'

    monkeypatch.setattr(api, "render_json", fake_render_json)
    monkeypatch.setattr(
        api,
        "build_single_target_report_document_from_run_target",
        lambda *a, **kw: MagicMock(),
    )

    api.generate_single_target_report_from_run_target(
        MagicMock(), MagicMock(), "json", config=None, markdown_mode="debug"
    )

    assert len(render_json_calls) == 1  # JSON renderer was called
    # markdown_mode does not appear in the JSON render call
    assert "markdown_mode" not in render_json_calls[0]


# ---------------------------------------------------------------------------
# Markdown single-target forwards resolved mode to render_markdown
# ---------------------------------------------------------------------------


def test_generate_single_target_markdown_forwards_mode(monkeypatch):
    render_calls: list[dict[str, Any]] = []

    def fake_render_markdown(document: Any, *, matching_debug_context=None, markdown_mode="standard") -> str:
        render_calls.append({"markdown_mode": markdown_mode})
        return "# report"

    monkeypatch.setattr(api, "render_markdown", fake_render_markdown)
    monkeypatch.setattr(
        api,
        "build_single_target_report_document_from_run_target",
        lambda *a, **kw: MagicMock(),
    )

    import pythonarchtesting.report.renderers.matching_debug as md_mod

    monkeypatch.setattr(
        md_mod, "build_multi_matching_debug_context", lambda *a, **kw: {}
    )

    api.generate_single_target_report_from_run_target(
        MagicMock(), MagicMock(), "markdown", config=None, markdown_mode="verbose"
    )

    assert render_calls[0]["markdown_mode"] == "verbose"


def test_generate_single_target_markdown_defaults_to_standard(monkeypatch):
    render_calls: list[dict[str, Any]] = []

    def fake_render_markdown(document: Any, *, matching_debug_context=None, markdown_mode="standard") -> str:
        render_calls.append({"markdown_mode": markdown_mode})
        return "# report"

    monkeypatch.setattr(api, "render_markdown", fake_render_markdown)
    monkeypatch.setattr(
        api,
        "build_single_target_report_document_from_run_target",
        lambda *a, **kw: MagicMock(),
    )

    import pythonarchtesting.report.renderers.matching_debug as md_mod

    monkeypatch.setattr(
        md_mod, "build_multi_matching_debug_context", lambda *a, **kw: {}
    )

    api.generate_single_target_report_from_run_target(
        MagicMock(), MagicMock(), "markdown", config=None
    )

    assert render_calls[0]["markdown_mode"] == "standard"


# ---------------------------------------------------------------------------
# Markdown multi-target forwards resolved mode to render_markdown_bundle
# ---------------------------------------------------------------------------


def test_generate_multi_target_markdown_forwards_mode(monkeypatch, tmp_path):
    render_calls: list[dict[str, Any]] = []

    def fake_render_markdown_bundle(document, output_dir, *, matching_debug_context=None, markdown_mode="standard"):
        render_calls.append({"markdown_mode": markdown_mode})
        return str(output_dir)

    monkeypatch.setattr(api, "render_markdown_bundle", fake_render_markdown_bundle)
    monkeypatch.setattr(
        api,
        "build_multi_target_report_document",
        lambda *a, **kw: MagicMock(),
    )

    import pythonarchtesting.report.renderers.matching_debug as md_mod

    monkeypatch.setattr(
        md_mod, "build_multi_matching_debug_context", lambda *a, **kw: {}
    )

    api.generate_multi_target_report(
        MagicMock(), [MagicMock()], "markdown", None, str(tmp_path), markdown_mode="debug"
    )

    assert render_calls[0]["markdown_mode"] == "debug"


# ---------------------------------------------------------------------------
# Lazy wrappers forward markdown_mode
# ---------------------------------------------------------------------------


def test_lazy_generate_single_target_forwards_markdown_mode(monkeypatch):
    calls: dict[str, Any] = {}

    def _fn(run_state, target_state, output_format, config, markdown_mode=None):
        calls["markdown_mode"] = markdown_mode
        return "ok"

    fake_module = SimpleNamespace(generate_single_target_report_from_run_target=_fn)
    monkeypatch.setattr(lazy, "_get_report_module", lambda: fake_module)

    lazy.generate_single_target_report_from_run_target(
        "run", "target", "markdown", None, markdown_mode="verbose"
    )
    assert calls["markdown_mode"] == "verbose"


def test_lazy_generate_multi_target_forwards_markdown_mode(monkeypatch):
    calls: dict[str, Any] = {}

    def _fn(run_state, target_states, output_format, config, output_path=None, markdown_mode=None):
        calls["markdown_mode"] = markdown_mode
        return "ok"

    fake_module = SimpleNamespace(generate_multi_target_report=_fn)
    monkeypatch.setattr(lazy, "_get_report_module", lambda: fake_module)

    lazy.generate_multi_target_report(
        "run", ["t1"], "markdown", None, markdown_mode="debug"
    )
    assert calls["markdown_mode"] == "debug"


def test_lazy_generate_validation_report_forwards_markdown_mode(monkeypatch):
    calls: dict[str, Any] = {}

    def _fn(state_obj, output_format, include_sections, config, markdown_mode=None):
        calls["markdown_mode"] = markdown_mode
        return "ok"

    fake_module = SimpleNamespace(generate_validation_report=_fn)
    monkeypatch.setattr(lazy, "_get_report_module", lambda: fake_module)

    lazy.generate_validation_report("state", "markdown", None, None, markdown_mode="verbose")
    assert calls["markdown_mode"] == "verbose"


# ---------------------------------------------------------------------------
# MarkdownReportGenerator forwards mode in both dispatch paths
# ---------------------------------------------------------------------------


def test_markdown_generator_single_target_forwards_mode(monkeypatch):
    from pythonarchtesting.report.markdown_generator import MarkdownReportGenerator
    from pythonarchtesting.report.presentation import MarkdownMode

    calls: dict[str, Any] = {}

    def fake_render_markdown_mode(document, *, mode, matching_debug_context=None):
        calls["mode"] = mode
        return "# result"

    monkeypatch.setattr(
        "pythonarchtesting.report.markdown_generator.render_markdown_mode",
        fake_render_markdown_mode,
    )

    doc = MagicMock()
    doc.kind = "single"
    gen = MarkdownReportGenerator(doc, markdown_mode="verbose")
    gen._ensure_document = lambda: doc  # type: ignore[method-assign]
    gen._generate_report()

    assert calls["mode"] == "verbose"


def test_markdown_generator_multi_target_forwards_mode(monkeypatch, tmp_path):
    from pathlib import Path

    from pythonarchtesting.report.markdown_generator import MarkdownReportGenerator

    calls: dict[str, Any] = {}

    def fake_render_bundle_mode(document, output_dir, *, mode, matching_debug_context=None):
        calls["mode"] = mode
        return str(output_dir)

    monkeypatch.setattr(
        "pythonarchtesting.report.markdown_generator.render_markdown_bundle_mode",
        fake_render_bundle_mode,
    )

    doc = MagicMock()
    doc.kind = "multi"
    gen = MarkdownReportGenerator(doc, markdown_mode="debug")
    gen._ensure_document = lambda: doc  # type: ignore[method-assign]
    gen._generate_report(output_file=str(tmp_path))

    assert calls["mode"] == "debug"
