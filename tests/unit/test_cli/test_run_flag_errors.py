"""Characterisation of the CLI's flag checks: which message wins, and in what order.

Most CLI tests only assert ``SystemExit``; these pin the exact ``parser.error``
text for each flag combination, so the precedence of the checks (ignored flags,
then the source, then the sandbox; ``--dynamic``, then the format, then target
flags, then the source) cannot drift unnoticed.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import pythonarchtesting.cli as cli

_IGNORED_ALL = (
    "--write-model describes the reference only and writes FILE; drop "
    "--target/--targets/--targets-dir, --project-pattern, --exclude-patterns, "
    "--validate-declarations, --architecture, --mapping, --output, --format."
)
_WRITE_MODEL_NO_SOURCE = (
    "--write-model requires --source or a configured [projects].source_path."
)
_SANDBOX_STATIC = "--sandbox and --sandbox-memory-mb apply only with --dynamic."
_SANDBOX_MEMORY = "--sandbox-memory-mb must be positive."
_VALIDATE_DYNAMIC = "--validate-declarations runs no target code; drop --dynamic."
_VALIDATE_FORMAT = "Declaration validation supports only --format json."
_VALIDATE_TARGETS = (
    "--validate-declarations is source-only and does not accept target "
    "selection flags."
)
_VALIDATE_NO_SOURCE = (
    "--validate-declarations requires --source, --reference-modules, "
    "or a configured [projects].source_path."
)
_MARKDOWN_OUTPUT = "Markdown reporting requires --output <directory>."


def _config(source_path=None):
    return SimpleNamespace(
        projects=SimpleNamespace(
            targets=[], targets_dir=None, target_path=None, source_path=source_path
        )
    )


@pytest.fixture
def calls(monkeypatch):
    """Stub everything past the flag checks and record what got called."""
    recorded: dict = {}
    monkeypatch.setattr(cli, "load_config", lambda **kwargs: _config())
    monkeypatch.setattr(cli, "configure_logging", lambda config: None)
    monkeypatch.setattr(cli, "resolve_projects_config", lambda **kwargs: None)

    def _write_model(config, args, source, sandbox):
        recorded["write_model"] = (source, sandbox)
        return 0

    def _validation(**kwargs):
        recorded["validation"] = kwargs
        return 0

    def _run_projects(**kwargs):
        recorded["run_projects"] = kwargs
        return SimpleNamespace(), []

    monkeypatch.setattr(cli, "_write_model", _write_model)
    monkeypatch.setattr(cli, "_run_declaration_validation", _validation)
    monkeypatch.setattr(cli, "run_projects", _run_projects)
    monkeypatch.setattr(cli, "generate_run_report", lambda *a: "REPORT")
    monkeypatch.setattr(cli, "get_run_exit_code", lambda *a: 7)
    return recorded


def _error_text(capsys, argv):
    with pytest.raises(SystemExit) as excinfo:
        cli._run(argv)
    assert excinfo.value.code == 2
    last = capsys.readouterr().err.strip().splitlines()[-1]
    return last.split(": error: ", 1)[1]


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            [
                "--write-model",
                "m.json",
                "--format",
                "markdown",
                "--output",
                "o",
                "--mapping",
                "p.json",
                "--architecture",
                "--validate-declarations",
                "--exclude-patterns",
                "x",
                "--project-pattern",
                "p*",
                "--target",
                "t",
            ],
            _IGNORED_ALL,
        ),
        (
            ["--write-model", "m.json", "--targets-dir", "d"],
            "--write-model describes the reference only and writes FILE; drop "
            "--target/--targets/--targets-dir.",
        ),
        (
            ["--write-model", "m.json", "--targets", "a,b", "--dynamic"],
            "--write-model describes the reference only and writes FILE; drop "
            "--target/--targets/--targets-dir.",
        ),
        # Ignored flags are reported before the missing source.
        (
            ["--write-model", "m.json", "--validate-declarations"],
            "--write-model describes the reference only and writes FILE; drop "
            "--validate-declarations.",
        ),
        (["--write-model", "m.json"], _WRITE_MODEL_NO_SOURCE),
        # The missing source is reported before the sandbox check.
        (["--write-model", "m.json", "--sandbox", "none"], _WRITE_MODEL_NO_SOURCE),
        (
            ["--write-model", "m.json", "--source", "s", "--sandbox", "none"],
            _SANDBOX_STATIC,
        ),
        (
            [
                "--write-model",
                "m.json",
                "--source",
                "s",
                "--dynamic",
                "--sandbox-memory-mb",
                "0",
            ],
            _SANDBOX_MEMORY,
        ),
        (
            [
                "--validate-declarations",
                "--dynamic",
                "--format",
                "markdown",
                "--target",
                "t",
            ],
            _VALIDATE_DYNAMIC,
        ),
        (
            ["--validate-declarations", "--format", "markdown", "--target", "t"],
            _VALIDATE_FORMAT,
        ),
        (["--validate-declarations", "--target", "t"], _VALIDATE_TARGETS),
        (["--validate-declarations", "--targets", "a"], _VALIDATE_TARGETS),
        (["--validate-declarations", "--targets-dir", "d"], _VALIDATE_TARGETS),
        (["--validate-declarations", "--project-pattern", "p"], _VALIDATE_TARGETS),
        (["--validate-declarations", "--exclude-patterns", "e"], _VALIDATE_TARGETS),
        (["--validate-declarations"], _VALIDATE_NO_SOURCE),
        (["--format", "markdown", "--sandbox", "none"], _MARKDOWN_OUTPUT),
        (["--sandbox", "none", "--mapping", "missing.json"], _SANDBOX_STATIC),
        (["--sandbox-memory-mb", "5"], _SANDBOX_STATIC),
    ],
)
def test_flag_errors_keep_their_text_and_precedence(calls, capsys, argv, message):
    assert _error_text(capsys, argv) == message
    assert calls == {}


def test_missing_mapping_file_is_reported_after_the_sandbox(calls, capsys, tmp_path):
    missing = tmp_path / "missing.json"
    text = _error_text(capsys, ["--mapping", str(missing)])
    assert text.startswith(f"--mapping {missing}: ")


def test_mapping_error_from_the_run_becomes_a_usage_error(calls, capsys, monkeypatch):
    def _raise(**kwargs):
        raise cli.MappingError("pair x is unknown")

    monkeypatch.setattr(cli, "run_projects", _raise)
    assert _error_text(capsys, []) == "pair x is unknown"


def test_write_model_uses_the_configured_source(calls, monkeypatch):
    monkeypatch.setattr(cli, "load_config", lambda **kwargs: _config("cfg"))
    assert cli._run(["--write-model", "m.json"]) == 0
    assert calls == {"write_model": ("cfg", None)}


def test_write_model_prefers_the_explicit_source(calls, monkeypatch):
    monkeypatch.setattr(cli, "load_config", lambda **kwargs: _config("cfg"))
    assert cli._run(["--write-model", "m.json", "--source", "s"]) == 0
    assert calls == {"write_model": ("s", None)}


def test_validation_falls_back_to_the_current_directory(calls):
    assert cli._run(["--validate-declarations", "--reference-modules", "a,b"]) == 0
    assert calls["validation"]["source_path"] == "."
    assert calls["validation"]["reference_modules"] == ["a", "b"]


def test_validation_uses_the_configured_source(calls, monkeypatch):
    monkeypatch.setattr(cli, "load_config", lambda **kwargs: _config(Path("cfg")))
    assert cli._run(["--validate-declarations", "--output", "o.json"]) == 0
    assert calls["validation"]["source_path"] == "cfg"
    assert calls["validation"]["output_file"] == "o.json"


def _set_counts(monkeypatch, skipped, unverified, undecided):
    import pythonarchtesting.runner.skips as skips

    monkeypatch.setattr(skips, "count_runtime_rules_skipped", lambda s: skipped)
    monkeypatch.setattr(skips, "count_runtime_results_unverified", lambda s: unverified)
    monkeypatch.setattr(skips, "count_results_undecided", lambda s: undecided)


def test_run_warns_about_every_unchecked_kind_in_order(calls, capsys, monkeypatch):
    _set_counts(monkeypatch, 1, 2, 3)
    assert cli._run([]) == 7
    captured = capsys.readouterr()
    assert captured.err.splitlines() == [
        "warning: 1 runtime rule result(s) were SKIPPED because --dynamic was "
        "not given; their targets are not checked by them",
        "warning: 2 runtime rule result(s) passed with code or cases left "
        "unchecked; see details.unverified",
        "warning: 3 result(s) passed with undecided architecture changes; "
        "see details.undecided",
    ]
    assert captured.out == "REPORT\n"


def test_run_stays_quiet_without_unchecked_results(calls, capsys, monkeypatch):
    _set_counts(monkeypatch, 0, 0, 0)
    assert cli._run([]) == 7
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    ("argv", "printed"),
    [
        (["--output", "r.json"], "Report written to r.json\n"),
        (["--output", "dir", "--format", "markdown"], "Report written to REPORT\n"),
        ([], "REPORT\n"),
    ],
)
def test_run_prints_where_the_report_went(calls, capsys, monkeypatch, argv, printed):
    _set_counts(monkeypatch, 0, 0, 0)
    assert cli._run(argv) == 7
    assert capsys.readouterr().out == printed
