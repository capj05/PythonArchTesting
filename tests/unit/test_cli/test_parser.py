import pytest

from src.cli import _parse_csv, build_parser


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
