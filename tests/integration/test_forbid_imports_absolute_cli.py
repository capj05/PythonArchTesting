"""``forbid_imports`` sees absolute imports through the project's own name.

A submission may import its modules relatively (``from .repository``), through
its own directory name (``from target.repository``) or through the reference's
package name (``from reference.repository``); all three are the same import.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pythonarchtesting.cli import main


def _controller(marker: str) -> str:
    return (
        "from typing import Annotated\n"
        "from pythonarchtesting.rules import forbid_imports\n\n"
        f"__archtest__: Annotated[None, {marker}]\n\n"
        "def handle():\n    return 1\n"
    )


_REPOSITORY = "class Repo:\n    pass\n"
# The service is allowed; in reachable mode it leads on to the repository.
_SERVICE = "from {via}repository import Repo\n\n\ndef make():\n    return Repo()\n"


def _status(tmp_path: Path, marker: str, files: dict[str, str]) -> str:
    reference = tmp_path / "reference"
    target = tmp_path / "target"
    for root, extra in (
        (reference, {"controller.py": _controller(marker)}),
        (target, files),
    ):
        root.mkdir()
        sources = {"__init__.py": "", "repository.py": _REPOSITORY, **extra}
        for name, text in sources.items():
            (root / name).write_text(text, encoding="utf-8")
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(reference),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    (status,) = [
        r["status"]
        for t in report["targets"]
        for r in t["results"]
        if "forbid_imports" in r["rule_id"]
    ]
    return str(status)


@pytest.mark.parametrize("via", [".", "target.", "reference."])
def test_a_direct_forbidden_import_fails_however_it_is_spelled(
    tmp_path: Path, via: str
):
    controller = (
        f"from {via}repository import Repo\n\n\ndef handle():\n    return Repo()\n"
    )

    assert (
        _status(
            tmp_path,
            'forbid_imports("repository", mode="direct")',
            {"controller.py": controller},
        )
        == "FAILED"
    )


@pytest.mark.parametrize("via", [".", "target.", "reference."])
def test_a_reachable_forbidden_import_fails_however_it_is_spelled(
    tmp_path: Path, via: str
):
    files = {
        "service.py": _SERVICE.format(via=via),
        "controller.py": f"from {via}service import make\n\n\n"
        "def handle():\n    return make()\n",
    }

    assert (
        _status(tmp_path, 'forbid_imports("repository", mode="reachable")', files)
        == "FAILED"
    )
