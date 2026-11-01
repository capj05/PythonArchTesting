"""Held-out variants written by an LLM, not by the author of ``mutants.py``.

The variants are in ``llm_variants.json`` next to this file, as the
generator wrote them (``id``, ``kind``, ``operator``, ``description``,
``patches``, optionally ``new_files``). Which markers state the intent a
mutant breaks is not the generator's call: ``detected_by`` is the union of
the hand-written mutants' ``detected_by`` for the same operator. Run with::

    python example/architectural_mutants/run.py --program <this directory> \
        --mutants <this directory>/llm_mutants.py
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent


def _hand_written() -> Any:
    spec = importlib.util.spec_from_file_location("_hand_mutants", _HERE / "mutants.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    detected: dict[str, set[str]] = {}
    for mutant in _hand_written().MUTANTS:
        detected.setdefault(mutant["operator"], set()).update(mutant["detected_by"])
    raw = json.loads((_HERE / "llm_variants.json").read_text(encoding="utf-8"))
    mutants, equivalents = [], []
    for item in raw:
        variant = {
            "id": str(item["id"]),
            "operator": str(item.get("operator") or "-"),
            "description": str(item["description"]),
            "patches": [tuple(patch) for patch in item.get("patches") or []],
        }
        if item.get("new_files"):
            variant["new_files"] = dict(item["new_files"])
        if item.get("kind") == "equivalent":
            variant["operator"] = "-"
            equivalents.append(variant)
        else:
            variant["detected_by"] = sorted(detected.get(variant["operator"], set()))
            mutants.append(variant)
    return mutants, equivalents


MUTANTS, EQUIVALENTS = _load()
