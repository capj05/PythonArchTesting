from __future__ import annotations

from types import SimpleNamespace

import pythonarchtesting.report.lazy as lazy


def test_generate_run_report_forwards_config(monkeypatch):
    calls = {}

    def _generate_run_report(
        run_state, target_states, output_format, config, output_path=None
    ):
        calls["args"] = (run_state, target_states, output_format, config, output_path)
        return "ok"

    fake_module = SimpleNamespace(generate_run_report=_generate_run_report)
    monkeypatch.setattr(lazy, "_get_report_module", lambda: fake_module)

    cfg = object()
    out = lazy.generate_run_report("run", ["t1"], "json", cfg)
    assert out == "ok"
    assert calls["args"] == ("run", ["t1"], "json", cfg, None)


def test_get_run_exit_code_forwards_config(monkeypatch):
    calls = {}

    def _get_run_exit_code(run_state, target_states, config):
        calls["args"] = (run_state, target_states, config)
        return 7

    fake_module = SimpleNamespace(get_run_exit_code=_get_run_exit_code)
    monkeypatch.setattr(lazy, "_get_report_module", lambda: fake_module)

    cfg = object()
    out = lazy.get_run_exit_code("run", ["t1"], cfg)
    assert out == 7
    assert calls["args"] == ("run", ["t1"], cfg)
