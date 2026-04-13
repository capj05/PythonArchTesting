from __future__ import annotations

from types import SimpleNamespace

import pythonarchtesting.report.lazy as lazy


def test_generate_validation_report_forwards_config(monkeypatch):
    calls = {}

    def _generate_validation_report(
        state_obj, output_format, include_sections, config, markdown_mode=None
    ):
        calls["args"] = (state_obj, output_format, include_sections, config)
        calls["markdown_mode"] = markdown_mode
        return "ok"

    fake_module = SimpleNamespace(
        generate_validation_report=_generate_validation_report
    )
    monkeypatch.setattr(lazy, "_get_report_module", lambda: fake_module)

    cfg = object()
    out = lazy.generate_validation_report("state", "json", ["summary"], cfg)
    assert out == "ok"
    assert calls["args"] == ("state", "json", ["summary"], cfg)
    assert calls["markdown_mode"] is None


def test_build_single_target_report_document_from_run_target_forwards_config(
    monkeypatch,
):
    calls = {}

    def _build_single_target_report_document_from_run_target(
        run_state, target_state, config
    ):
        calls["args"] = (run_state, target_state, config)
        return "doc"

    fake_module = SimpleNamespace(
        build_single_target_report_document_from_run_target=(
            _build_single_target_report_document_from_run_target
        )
    )
    monkeypatch.setattr(lazy, "_get_report_module", lambda: fake_module)

    cfg = object()
    out = lazy.build_single_target_report_document_from_run_target("run", "target", cfg)
    assert out == "doc"
    assert calls["args"] == ("run", "target", cfg)


def test_build_single_target_report_from_run_target_forwards_config(monkeypatch):
    calls = {}

    def _build_single_target_report_from_run_target(run_state, target_state, config):
        calls["args"] = (run_state, target_state, config)
        return {"ok": True}

    fake_module = SimpleNamespace(
        build_single_target_report_from_run_target=(
            _build_single_target_report_from_run_target
        )
    )
    monkeypatch.setattr(lazy, "_get_report_module", lambda: fake_module)

    cfg = object()
    out = lazy.build_single_target_report_from_run_target("run", "target", cfg)
    assert out == {"ok": True}
    assert calls["args"] == ("run", "target", cfg)


def test_generate_single_target_report_from_run_target_forwards_config(monkeypatch):
    calls = {}

    def _generate_single_target_report_from_run_target(
        run_state, target_state, output_format, config, markdown_mode=None
    ):
        calls["args"] = (run_state, target_state, output_format, config)
        calls["markdown_mode"] = markdown_mode
        return "ok"

    fake_module = SimpleNamespace(
        generate_single_target_report_from_run_target=(
            _generate_single_target_report_from_run_target
        )
    )
    monkeypatch.setattr(lazy, "_get_report_module", lambda: fake_module)

    cfg = object()
    out = lazy.generate_single_target_report_from_run_target(
        "run", "target", "json", cfg
    )
    assert out == "ok"
    assert calls["args"] == ("run", "target", "json", cfg)
    assert calls["markdown_mode"] is None


def test_generate_multi_target_report_forwards_config(monkeypatch):
    calls = {}

    def _generate_multi_target_report(
        run_state, target_states, output_format, config, output_path=None, markdown_mode=None
    ):
        calls["args"] = (run_state, target_states, output_format, config, output_path)
        calls["markdown_mode"] = markdown_mode
        return "ok"

    fake_module = SimpleNamespace(
        generate_multi_target_report=_generate_multi_target_report
    )
    monkeypatch.setattr(lazy, "_get_report_module", lambda: fake_module)

    cfg = object()
    out = lazy.generate_multi_target_report("run", ["t1"], "json", cfg)
    assert out == "ok"
    assert calls["args"] == ("run", ["t1"], "json", cfg, None)
    assert calls["markdown_mode"] is None


def test_get_multi_exit_code_forwards_config(monkeypatch):
    calls = {}

    def _get_multi_exit_code(run_state, target_states, config):
        calls["args"] = (run_state, target_states, config)
        return 7

    fake_module = SimpleNamespace(get_multi_exit_code=_get_multi_exit_code)
    monkeypatch.setattr(lazy, "_get_report_module", lambda: fake_module)

    cfg = object()
    out = lazy.get_multi_exit_code("run", ["t1"], cfg)
    assert out == 7
    assert calls["args"] == ("run", ["t1"], cfg)
