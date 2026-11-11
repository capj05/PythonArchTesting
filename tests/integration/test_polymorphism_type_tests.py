"""``type_switch`` and ``type_comparison`` only for a client that branches on
the class of an object (review of N4): validating input against builtin
types, or showing a type's name, is no finding; a test against a variant
class still is, also in a helper of the client's module."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from pythonarchtesting.cli import main
from pythonarchtesting.principles import classify_target, get_principle

_TASK = Path(__file__).resolve().parents[2] / "example" / "principles" / "polymorphism"

_HEADER = (
    "from __future__ import annotations\n\nfrom .shapes import Circle, Shape\n\n\n"
)
_DESCRIBE = (
    "def describe_all(shapes: list[Shape]) -> str:\n"
    '    lines = [f"{shape.describe()}: plocha {shape.area():.2f}" for shape in shapes]\n'
    '    return "\\n".join(lines)\n'
)
_TOTAL = (
    "def total_area(shapes: list[Shape]) -> float:\n"
    "    total = 0.0\n"
    "    for shape in shapes:\n"
    "        total += shape.area()\n"
    "    return total\n\n\n"
)
_CLIENTS = {
    "validate_list": _HEADER
    + _TOTAL.replace(
        "    total = 0.0\n",
        "    if not isinstance(shapes, list):\n"
        '        raise TypeError("a list")\n'
        "    total = 0.0\n",
    )
    + _DESCRIBE,
    "validate_number": _HEADER
    + _TOTAL.replace(
        "        total += shape.area()\n",
        "        a = shape.area()\n"
        "        if isinstance(a, (int, float)):\n"
        "            total += a\n",
    )
    + _DESCRIBE,
    "type_name_shown": _HEADER
    + _TOTAL
    + _DESCRIBE.replace(
        'f"{shape.describe()}', 'f"{type(shape).__name__} {shape.describe()}'
    ),
    "helper_tests_class": _HEADER + "def _area(shape):\n"
    "    if isinstance(shape, Circle):\n"
    "        return shape.area()\n"
    "    return shape.area()\n\n\n"
    + _TOTAL.replace("shape.area()", "_area(shape)")
    + _DESCRIBE,
    "type_name_compared": _HEADER
    + _TOTAL
    + _DESCRIBE.replace(
        "    lines = ",
        '    _ = [s for s in shapes if type(s).__name__ == "Circle"]\n    lines = ',
    ),
}
_EXPECTED = {
    "validate_list": [],
    "validate_number": [],
    "type_name_shown": [],
    "helper_tests_class": ["type_switch"],
    "type_name_compared": ["type_comparison"],
}


@pytest.mark.parametrize("variant", sorted(_CLIENTS))
def test_only_a_test_of_the_class_is_a_finding(tmp_path: Path, variant: str) -> None:
    if variant == "type_name_compared" and sys.version_info < (3, 12):
        pytest.skip("a call of type() is observed from Python 3.12 on")
    submission = tmp_path / variant
    shutil.copytree(_TASK / "assignments" / "ok_basic", submission)
    (submission / "report.py").write_text(_CLIENTS[variant], encoding="utf-8")
    output = tmp_path / "report.json"

    main(
        [
            "--source",
            str(_TASK),
            "--target",
            str(submission),
            "--format",
            "json",
            "--output",
            str(output),
            "--dynamic",
        ]
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    findings = classify_target(
        get_principle("polymorphism"), report["targets"][0]["results"]
    )
    assert [f.error_id for f in findings] == _EXPECTED[variant]
