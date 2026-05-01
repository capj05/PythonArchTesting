from __future__ import annotations

from pythonarchtesting.execution.glob_match import path_matches_any_glob


def test_no_patterns_returns_false() -> None:
    assert path_matches_any_glob("foo.py", None) is False
    assert path_matches_any_glob("foo.py", []) is False
    assert path_matches_any_glob("foo.py", ()) is False


def test_double_star_prefix_matches_at_any_depth() -> None:
    pattern = "**/ignored_module.py"
    assert path_matches_any_glob("ignored_module.py", [pattern]) is True
    assert path_matches_any_glob("a/ignored_module.py", [pattern]) is True
    assert path_matches_any_glob("a/b/ignored_module.py", [pattern]) is True
    assert path_matches_any_glob("ignored_module.pyc", [pattern]) is False
    assert path_matches_any_glob("other.py", [pattern]) is False


def test_double_star_in_middle_matches_zero_or_more_segments() -> None:
    pattern = "pkg/**/helper.py"
    assert path_matches_any_glob("pkg/helper.py", [pattern]) is True
    assert path_matches_any_glob("pkg/a/helper.py", [pattern]) is True
    assert path_matches_any_glob("pkg/a/b/helper.py", [pattern]) is True
    assert path_matches_any_glob("other/helper.py", [pattern]) is False


def test_trailing_double_star_matches_anything_below() -> None:
    pattern = "pkg/**"
    assert path_matches_any_glob("pkg", [pattern]) is True
    assert path_matches_any_glob("pkg/a.py", [pattern]) is True
    assert path_matches_any_glob("pkg/a/b.py", [pattern]) is True
    assert path_matches_any_glob("other/a.py", [pattern]) is False


def test_single_star_does_not_cross_path_separator() -> None:
    pattern = "*.py"
    assert path_matches_any_glob("foo.py", [pattern]) is True
    assert path_matches_any_glob("a/foo.py", [pattern]) is False


def test_directory_scoped_star() -> None:
    pattern = "pkg/*.py"
    assert path_matches_any_glob("pkg/a.py", [pattern]) is True
    assert path_matches_any_glob("pkg/sub/a.py", [pattern]) is False
    assert path_matches_any_glob("a.py", [pattern]) is False


def test_question_mark_matches_single_non_separator() -> None:
    pattern = "pkg/a?.py"
    assert path_matches_any_glob("pkg/ab.py", [pattern]) is True
    assert path_matches_any_glob("pkg/a.py", [pattern]) is False
    assert path_matches_any_glob("pkg/a/b.py", [pattern]) is False


def test_literal_match() -> None:
    pattern = "pkg/foo.py"
    assert path_matches_any_glob("pkg/foo.py", [pattern]) is True
    assert path_matches_any_glob("pkg/foo.pyc", [pattern]) is False


def test_any_of_multiple_patterns_matches() -> None:
    patterns = ["**/skipped.py", "vendor/**"]
    assert path_matches_any_glob("a/skipped.py", patterns) is True
    assert path_matches_any_glob("vendor/lib.py", patterns) is True
    assert path_matches_any_glob("src/main.py", patterns) is False


def test_freestanding_double_star_matches_any_path() -> None:
    pattern = "**"
    assert path_matches_any_glob("foo.py", [pattern]) is True
    assert path_matches_any_glob("a/b/c.py", [pattern]) is True
    assert path_matches_any_glob("", [pattern]) is True


def test_dot_in_pattern_is_literal() -> None:
    # `.` should match a literal dot, not "any character".
    assert path_matches_any_glob("foo.py", ["foo.py"]) is True
    assert path_matches_any_glob("fooXpy", ["foo.py"]) is False
