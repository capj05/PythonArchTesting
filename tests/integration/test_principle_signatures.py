"""The declarative signature of every catalogue error matches the failure of its
example variant (``example/principles/<p>/assignments/<variant>``) under the tool,
on every key the signature declares."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pythonarchtesting.cli import main
from pythonarchtesting.principles import (
    fact_signature,
    get_principle,
    signature_matches,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    tomllib = pytest.importorskip("tomli")

_EXAMPLES = Path(__file__).resolve().parents[2] / "example" / "principles"


def _detected_errors() -> list[tuple[str, str, str, str]]:
    """(principle, error id, marker, example variant) of every detected error."""
    found = []
    for pointer in sorted(_EXAMPLES.glob("*/principle.toml")):
        data = tomllib.loads(pointer.read_text(encoding="utf-8"))
        for error in get_principle(data["id"]).errors:
            if error.detected_by is not None:
                found.append(
                    (
                        pointer.parent.name,
                        error.id,
                        error.detected_by,
                        data["examples"][error.id],
                    )
                )
    return found


@pytest.mark.parametrize(
    ("principle", "error_id", "marker", "variant"), _detected_errors()
)
def test_declared_signature_matches_the_example_variant(
    tmp_path: Path, principle: str, error_id: str, marker: str, variant: str
) -> None:
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(_EXAMPLES / principle),
            "--target",
            str(_EXAMPLES / principle / "assignments" / variant),
            "--format",
            "json",
            "--output",
            str(output),
            "--dynamic",
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    failure = next(
        result
        for target in report["targets"]
        for result in target["results"]
        if result["status"] == "FAILED" and marker in result["rule_id"]
    )
    fact = ((failure.get("details") or {}).get("facts") or [{}])[0]
    error = next(e for e in get_principle(principle).errors if e.id == error_id)
    assert error.signature is not None
    assert signature_matches(error.signature.as_dict(), fact_signature(fact))


def test_every_principle_has_an_example_pointer() -> None:
    assert len(_detected_errors()) == 8
