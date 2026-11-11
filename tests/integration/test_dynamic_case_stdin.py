"""``main()`` that reads the keyboard can be checked with ``"stdin"`` in its cases.

Without it, ``input()`` in the target ends in ``EOFError`` before ``main``
calls anything, so "``main`` delegates to the logic" cannot be checked. The
prompt ``input()`` prints must not end up in the probe's JSON answer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pythonarchtesting.cli import main

_LOGIC = """
def double(x):
    return x * 2
"""

_REFERENCE_APP = """
from typing import Annotated

from pythonarchtesting.rules import require_runtime_calls

from . import logic


def main() -> None:
    __archtest__: Annotated[  # noqa: F842
        None,
        require_runtime_calls("logic", cases=[{"args": [], "stdin": "4\\n"}]),
    ]
    x = input("výzva: ")
    print(logic.double(int(x)))
"""

_TARGETS = {
    "delegates": """
from . import logic


def main():
    x = input("výzva: ")
    print(logic.double(int(x)))
""",
    "computes_itself": """
def main():
    x = input("výzva: ")
    print(int(x) * 2)
""",
}


def _write(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _verdict(tmp_path: Path, target: str) -> dict:
    reference = _write(
        tmp_path / "reference", {"logic.py": _LOGIC, "app.py": _REFERENCE_APP}
    )
    solution = _write(
        tmp_path / target, {"logic.py": _LOGIC, "app.py": _TARGETS[target]}
    )
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(reference),
            "--target",
            str(solution),
            "--format",
            "json",
            "--output",
            str(output),
            "--dynamic",
        ]
    )
    found: list[dict] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if str(node.get("rule_id", "")).startswith("DYN001") and "status" in node:
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(output.read_text(encoding="utf-8")))
    (result,) = found
    return result


@pytest.mark.parametrize(
    ("target", "status"), [("delegates", "OK"), ("computes_itself", "FAILED")]
)
def test_require_runtime_calls_with_stdin(
    tmp_path: Path, target: str, status: str
) -> None:
    result = _verdict(tmp_path, target)

    assert result["status"] == status, result["details"].get("summary")
    if status == "FAILED":
        assert "no direct call into logic" in result["details"]["summary"]


def test_input_prompt_keeps_probe_json_valid(tmp_path: Path) -> None:
    result = _verdict(tmp_path, "delegates")

    # A prompt in the probe's answer would make it unreadable: the rule would
    # end as an error instead of a verdict on the calls.
    assert result["status"] == "OK", result["details"]
    assert "raised" not in json.dumps(result["details"])
