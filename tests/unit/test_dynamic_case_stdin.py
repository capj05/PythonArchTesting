"""``"stdin"`` in a case: the text the target reads from the keyboard.

The probe swaps ``sys.stdin`` for the case's text while that one case runs and
puts the original back afterwards, so input never carries over to the next
case or job. Input the case does not consume is dropped; reading past its end
raises ``EOFError``, reported like any other exception, and what the target
did before it is still observed.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.dynamic.runner import run_case_batch, run_cases

_TARGET = """
import sys

from . import logic


def ask():
    return logic.double(int(input("n: ")))


def ask_twice():
    first = logic.double(int(input("n: ")))
    return first + int(input("again: "))


def read_line():
    raise LookupError(repr(sys.stdin.readline()))


def read_all():
    raise LookupError(repr(sys.stdin.read()))
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    package = tmp_path / "stdin_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "logic.py").write_text(
        "def double(x):\n    return x * 2\n", encoding="utf-8"
    )
    (package / "target.py").write_text(textwrap.dedent(_TARGET), encoding="utf-8")
    return package


def _run(root: Path, qualname: str, cases: list[dict[str, Any]]) -> list[dict]:
    outcome = run_cases(
        target_root=root,
        module_path="target",
        qualname=qualname,
        kind="function",
        cases=cases,
        init=None,
        timeout_s=10.0,
        observe={"calls": True},
    )
    assert outcome.status == "completed", outcome.error
    return outcome.cases


def _logic_calls(case: dict) -> list[dict]:
    return [call for call in case.get("calls") or [] if call["module"] == "logic"]


def test_input_reads_the_case_stdin(root: Path) -> None:
    (case,) = _run(root, "ask", [{"args": [], "stdin": "4\n"}])

    assert "raised" not in case, case
    assert _logic_calls(case)


def test_stdin_does_not_leak_between_cases(root: Path) -> None:
    first, second = _run(
        root, "ask", [{"args": [], "stdin": "4\nleft over\n"}, {"args": []}]
    )

    assert "raised" not in first, first
    assert second["raised"].startswith("EOFError"), second
    assert not _logic_calls(second)


def test_stdin_does_not_leak_between_jobs_of_a_batch(root: Path) -> None:
    def job(job_id: str, case: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": job_id,
            "qualname": "ask",
            "kind": "function",
            "cases": [case],
            "init": None,
            "timeout_s": 10.0,
            "observe": {"calls": True},
        }

    outcome = run_case_batch(
        target_root=root,
        module_path="target",
        jobs=[job("0", {"args": [], "stdin": "4\nleft over\n"}), job("1", {})],
    )

    assert outcome.status == "completed", outcome.error
    first = outcome.jobs["0"]["cases"][0]
    second = outcome.jobs["1"]["cases"][0]
    assert "raised" not in first, first
    assert second["raised"].startswith("EOFError"), second


def test_exhausted_stdin_raises_eoferror_after_what_already_ran(root: Path) -> None:
    (case,) = _run(root, "ask_twice", [{"args": [], "stdin": "4\n"}])

    assert case["raised"].startswith("EOFError"), case
    assert _logic_calls(case)


def test_stdin_read_directly(root: Path) -> None:
    (line,) = _run(root, "read_line", [{"args": [], "stdin": "first\nsecond\n"}])
    (text,) = _run(root, "read_all", [{"args": [], "stdin": "first\nsecond\n"}])

    assert line["raised"] == "LookupError: 'first\\n'"
    assert text["raised"] == "LookupError: 'first\\nsecond\\n'"
