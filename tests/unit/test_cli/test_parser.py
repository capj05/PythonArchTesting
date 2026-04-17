import pytest

from pythonarchtesting.cli import _parse_csv, build_parser


def test_parse_csv_strips_and_ignores_empty():
    assert _parse_csv(" a, ,b ,") == ["a", "b"]


def test_parse_csv_none_returns_empty():
    assert _parse_csv(None) == []
    assert _parse_csv("") == []


def test_build_parser_parses_targets_and_format():
    parser = build_parser()
    args = parser.parse_args(
        [
            "--target",
            "a",
            "--target",
            "b",
            "--targets",
            "c,d",
            "--format",
            "json",
        ]
    )

    assert args.target == ["a", "b"]
    assert args.targets == "c,d"
    assert args.format == "json"


def test_build_parser_default_format_is_json():
    parser = build_parser()
    args = parser.parse_args(["--target", "a"])
    assert args.format == "json"


def test_build_parser_rejects_report_format_alias():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--report-format", "json"])


def test_build_parser_rejects_removed_runtime_flags():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--target",
                "a",
                "--runtime-isolation",
                "unsafe",
                "--runtime-max-probe-modules",
                "7",
                "--runtime-fast",
                "--allow-unsafe-probes",
            ]
        )


def test_build_parser_validation_scope_flag():
    parser = build_parser()
    args = parser.parse_args(
        [
            "--target",
            "a",
            "--validation-scope",
            "logical-views",
        ]
    )

    assert args.validation_scope == "logical-views"


def test_build_parser_validate_declarations_flag():
    parser = build_parser()
    args = parser.parse_args(
        [
            "--validate-declarations",
            "--source",
            "reference",
            "--format",
            "json",
        ]
    )

    assert args.validate_declarations is True
    assert args.source == "reference"
    assert args.format == "json"


def test_build_parser_markdown_mode_verbose():
    parser = build_parser()
    args = parser.parse_args(
        ["--target", "a", "--format", "markdown", "--markdown-mode", "verbose"]
    )
    assert args.markdown_mode == "verbose"


def test_build_parser_markdown_mode_debug():
    parser = build_parser()
    args = parser.parse_args(
        ["--target", "a", "--format", "markdown", "--markdown-mode", "debug"]
    )
    assert args.markdown_mode == "debug"


def test_build_parser_markdown_mode_standard():
    parser = build_parser()
    args = parser.parse_args(
        ["--target", "a", "--format", "markdown", "--markdown-mode", "standard"]
    )
    assert args.markdown_mode == "standard"


def test_build_parser_markdown_mode_default_is_none():
    parser = build_parser()
    args = parser.parse_args(["--target", "a", "--format", "markdown"])
    assert args.markdown_mode is None


def test_build_parser_markdown_mode_rejects_invalid_choice():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--target", "a", "--format", "markdown", "--markdown-mode", "fancy"])


def test_main_rejects_markdown_mode_with_json_format(monkeypatch):
    from pythonarchtesting.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--target", "a", "--format", "json", "--markdown-mode", "verbose"])
    assert exc_info.value.code != 0
