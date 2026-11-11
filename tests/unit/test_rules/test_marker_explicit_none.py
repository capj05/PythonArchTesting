"""An argument given as ``None`` is the same as leaving it out.

The marker helpers default these arguments to ``None``; a declaration that
spells the default out must compile to the same rules, not be refused (a list
argument) or take another path (``enforce_flow`` with ``cases=None`` is no
runtime check).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.config.loader import load_config
from pythonarchtesting.rules.compilation import compile_rules
from pythonarchtesting.runner.source_prep import prepare_source
from tests.unit.test_rules import test_marker_invalid_severity as package

# marker -> (its declaration in the package, the same with the default spelt out)
_SPELT_OUT = {
    "enforce_layers": (
        'enforce_layers("app", "models", severity=SEV)',
        'enforce_layers("app", "models", closed=None, severity=SEV)',
    ),
    "forbid_private_access": (
        "forbid_private_access(severity=SEV)",
        "forbid_private_access(allow=None, severity=SEV)",
    ),
    "enforce_flow": (
        'enforce_flow(["raw", "normalized"], variable="value", severity=SEV)',
        'enforce_flow(["raw", "normalized"], variable="value", cases=None, '
        "init=None, severity=SEV)",
    ),
}


def _compile(tmp_path: Path, app: str) -> tuple[list[Any], list[Any]]:
    root = tmp_path / "pkg"
    root.mkdir(parents=True)
    for name, text in (
        ("__init__.py", package._INIT),
        ("models.py", package._MODELS),
        ("app.py", app),
    ):
        (root / name).write_text(text.replace("SEV", '"error"'), encoding="utf-8")
    config = load_config()
    state = prepare_source(config=config, source_path=root)
    rules, evidence, _ = compile_rules(list(state.source_entities), config)
    return rules, evidence


def _summary(rules: list[Any], marker: str) -> list[tuple[str, str]]:
    return sorted(
        (rule.rule_id, rule.rule_type)
        for rule in rules
        if rule.name == marker or rule.params.get("decorator") == marker
    )


@pytest.mark.parametrize("marker", sorted(_SPELT_OUT))
def test_an_explicit_none_compiles_as_the_left_out_argument(
    tmp_path: Path, marker: str
) -> None:
    written, spelt_out = _SPELT_OUT[marker]
    assert written in package._APP

    left_out, _ = _compile(tmp_path / "left_out", package._APP)
    rules, evidence = _compile(
        tmp_path / "spelt_out", package._APP.replace(written, spelt_out, 1)
    )

    assert _summary(rules, marker) == _summary(left_out, marker)
    assert "compiler_invalid_param" not in {rule.rule_type for rule in rules}
    assert [item for item in evidence if item.payload.get("issue")] == []
