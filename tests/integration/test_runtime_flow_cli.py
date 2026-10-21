"""CLI-level tests for ``enforce_flow(..., cases=[...])``."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from pythonarchtesting.cli import main

_STEPS = """
def parse(line):
    return line.split(";")


def validate(fields):
    if not fields:
        raise ValueError("empty")
    return fields


def store(fields, sink):
    sink.append(fields)
"""

_REFERENCE = """
from typing import Annotated

from pythonarchtesting.rules import enforce_flow, flow

from . import steps


def run(line: str, sink: list) -> list:
    record = line
    __archtest__: Annotated[None, flow("received", variable="record")]
    record = steps.parse(record)
    __archtest__: Annotated[None, flow("parsed", variable="record")]  # noqa: F811
    record = steps.validate(record)
    __archtest__: Annotated[None, flow("validated", variable="record")]  # noqa: F811
    steps.store(record, sink)
    __archtest__: Annotated[None, flow("stored", variable="record")]  # noqa: F811
    __archtest__: Annotated[  # noqa: F811
        None,
        enforce_flow(
            ["received", "parsed", "validated", "stored"],
            variable="record",
            cases=[{"args": ["ada;36", []]}],
        ),
    ]
    return record
"""


def _target(body: str) -> str:
    return "from . import steps\n\n\ndef run(line, sink):\n" + textwrap.indent(
        textwrap.dedent(body).strip(), "    "
    )


_IN_ORDER = _target("""
    fields = steps.parse(line)
    print(len(fields))
    steps.store(steps.validate(fields), sink)
    return fields
    """)


def _project(
    tmp_path: Path,
    target: str,
    reference: str = _REFERENCE,
    target_steps: str = _STEPS,
) -> tuple[Path, Path]:
    reference_dir = tmp_path / "reference"
    target_dir = tmp_path / "target"
    for package, pipeline, steps in (
        (reference_dir, reference, _STEPS),
        (target_dir, target, target_steps),
    ):
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "pipeline.py").write_text(
            textwrap.dedent(pipeline), encoding="utf-8"
        )
        (package / "steps.py").write_text(textwrap.dedent(steps), encoding="utf-8")
    return reference_dir, target_dir


def _flow_rows(tmp_path: Path, reference: Path, target: Path) -> tuple[int, list]:
    output = tmp_path / "report.json"
    exit_code = main(
        [
            "--source",
            str(reference),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(output),
            "--dynamic",
        ]
    )
    rows: list = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if str(node.get("rule_id", "")).startswith("FLW002/"):
                rows.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(output.read_text(encoding="utf-8")))
    return exit_code, rows


def _check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], *args: str
) -> tuple[int, list]:
    reference, target = _project(tmp_path, *args)
    exit_code, rows = _flow_rows(tmp_path, reference, target)
    capsys.readouterr()
    return exit_code, rows


def test_a_target_without_markers_passes_when_it_calls_the_steps_in_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Other calls in between (print) do not matter.
    exit_code, rows = _check(tmp_path, capsys, _IN_ORDER)

    assert exit_code == 0
    assert [row["status"] for row in rows] == ["OK"]
    # "received" calls no project function and cannot be told apart.
    assert "stage(s) 'received' call no project function" in rows[0]["message"]


def test_a_target_that_computes_other_values_still_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other_steps = _STEPS.replace('line.split(";")', "[line.upper()]")

    exit_code, rows = _check(tmp_path, capsys, _IN_ORDER, _REFERENCE, other_steps)

    assert exit_code == 0
    assert [row["status"] for row in rows] == ["OK"]


def test_a_target_that_skips_a_stage_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _target("""
        fields = steps.parse(line)
        steps.store(fields, sink)
        return fields
        """)

    exit_code, rows = _check(tmp_path, capsys, target)

    assert exit_code == 1
    assert [row["status"] for row in rows] == ["FAILED"]
    assert "stage 'validated' calls validate()" in rows[0]["message"]
    assert "the target never calls it" in rows[0]["message"]


def test_a_target_that_reorders_the_stages_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _target("""
        steps.validate([line])
        fields = steps.parse(line)
        steps.store(fields, sink)
        return fields
        """)

    exit_code, rows = _check(tmp_path, capsys, target)

    assert exit_code == 1
    assert [row["status"] for row in rows] == ["FAILED"]
    assert "the target calls it only earlier" in rows[0]["message"]


def test_a_renamed_step_is_matched_to_its_reference_function(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    renamed = _STEPS.replace("def validate(", "def validate_fields(")
    target = _IN_ORDER.replace("steps.validate(", "steps.validate_fields(")

    exit_code, rows = _check(tmp_path, capsys, target, _REFERENCE, renamed)

    assert exit_code == 0
    assert [row["status"] for row in rows] == ["OK"]


def test_a_target_that_raises_is_judged_on_the_calls_it_made(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _target("""
        steps.parse(line)
        raise RuntimeError("stop")
        """)

    exit_code, rows = _check(tmp_path, capsys, target)

    assert exit_code == 1
    assert [row["status"] for row in rows] == ["FAILED"]
    assert "the call raised RuntimeError: stop" in rows[0]["message"]


def test_a_reference_whose_stages_call_nothing_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reference = (
        _REFERENCE.replace("steps.parse(record)", 'record.split(";")')
        .replace("steps.validate(record)", "list(record)")
        .replace("steps.store(record, sink)", "sink.append(record)")
    )

    exit_code, rows = _check(tmp_path, capsys, _IN_ORDER, reference)

    assert exit_code == 1
    assert [row["status"] for row in rows] == ["ERROR"]
    assert "no stage of the reference calls a function" in rows[0]["message"]


def test_a_case_that_skips_a_stage_in_the_reference_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The "validated" marker sits inside the "if", which the case never enters.
    marker = '__archtest__: Annotated[None, flow("validated", variable="record")]'
    reference = _REFERENCE.replace(
        f"    record = steps.validate(record)\n    {marker}",
        f"    if len(record) > 5:\n        record = steps.validate(record)\n"
        f"        {marker}",
    )
    assert reference != _REFERENCE

    exit_code, rows = _check(tmp_path, capsys, _IN_ORDER, reference)

    assert exit_code == 1
    assert [row["status"] for row in rows] == ["ERROR"]
    assert "never reaches stage(s) validated in the reference" in rows[0]["message"]


def test_a_reference_that_raises_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reference = _REFERENCE.replace('"ada;36"', '""').replace(
        "steps.parse(record)", "[]"
    )

    exit_code, rows = _check(tmp_path, capsys, _IN_ORDER, reference)

    assert exit_code == 1
    assert [row["status"] for row in rows] == ["ERROR"]
    assert "the reference itself did not run" in rows[0]["message"]


_METHOD_REFERENCE = """
from typing import Annotated

from pythonarchtesting.rules import enforce_flow, flow

from . import steps


class Importer:
    def __init__(self, separator: str) -> None:
        self.separator = separator

    def run(self, line: str, sink: list) -> list:
        record = steps.parse(line + self.separator)
        __archtest__: Annotated[None, flow("parsed", variable="record")]
        steps.store(steps.validate(record), sink)
        __archtest__: Annotated[None, flow("stored", variable="record")]  # noqa: F811
        __archtest__: Annotated[  # noqa: F811
            None,
            enforce_flow(
                ["parsed", "stored"],
                variable="record",
                cases=[{"args": ["ada", []]}],
                init={"args": [";"]},
            ),
        ]
        return record
"""

_METHOD_TARGET = """
from . import steps


class Importer:
    def __init__(self, separator):
        self.separator = separator

    def run(self, line, sink):
        fields = steps.parse(line + self.separator)
        steps.store(steps.validate(fields), sink)
        return fields
"""


def test_init_builds_the_instance_for_a_method_in_both_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code, rows = _check(tmp_path, capsys, _METHOD_TARGET, _METHOD_REFERENCE)

    assert exit_code == 0
    assert [row["status"] for row in rows] == ["OK"]
