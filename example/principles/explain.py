"""Shared by ``verify.py`` and ``pilot/run_tool.py``: run the tool, explain a failure.

The student explanation of a failed rule is composed from a catalogue error's
``what`` / ``why`` / ``fix`` and the facts of the report, without any LLM:
``what`` may use the target's ``{function}``, ``{file}`` and ``{line}``, and the
first fact of ``details.facts``: ``{caller}``, ``{callee}``, ``{module}``,
``{class}``, ``{attribute}``, ``{change}`` (in Czech), ``{fact_file}`` and
``{fact_line}``; and three derived ones: ``{callee_short}`` (the callee as a
beginner writes it: ``print()``, ``input()``, ``open()``, otherwise
``module.name()``), ``{via_last}`` (the last step of a detour, the helper that
made the call, e.g. ``messages:warn``) and ``{via_first_line}`` (the line of
the target's function the detour starts at). A placeholder the fact lacks
becomes ``?``.

For a submission whose error is not known in advance (the pilot), the error
that explains a failure is the catalogue error of the failing marker whose own
example failed with the most similar first fact (``choose_error``).

Needs Python 3.11+ (tomllib); the tool itself supports 3.10.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

CLI = Path(sys.executable).with_name("python-arch-test")
# Rule failures that are no verdict on the code: the matching found no target.
NO_MATCH = "required_target_missing"
# How a write changed the attribute (``change`` of a ``write`` fact), in Czech.
_CHANGE_CS = {
    "assigned": "přiřazuje",
    "mutated": "mění obsah",
    "deleted": "maže",
    "bypassed": "přiřazuje mimo `__setattr__`",
}
_FACT_KEYS = ("caller", "callee", "module", "class", "attribute")
# Callees a beginner knows by their bare name, not by their module.
_BARE_CALLEES = {"builtins:print": "print", "builtins:input": "input", "io:open": "open"}
# Fact keys that tell one error of a marker from another. Not the names a
# submission chooses (functions, modules) nor those of the catalogue's own task
# (attributes, classes): a solution written by an agent names them differently.
# Of an attribute only whether it is private (``_name``) counts.
_SIGNATURE_KEYS = ("kind", "callee", "change")


class _Placeholders(dict):
    """Values for ``str.format_map``; a missing placeholder reads ``?``."""

    def __missing__(self, key: str) -> str:
        return "?"


def load_entry(principle_dir: Path) -> dict[str, Any]:
    """The catalogue entry ``<principle>/principle.toml``."""
    return tomllib.loads((principle_dir / "principle.toml").read_text(encoding="utf-8"))


def run_catalogue(principle_dir: Path) -> dict[str, list[dict]]:
    """Run the tool over the principle's variants; results per variant name."""
    command = [
        str(CLI),
        "--source", str(principle_dir / "reference"),
        "--targets-dir", str(principle_dir / "assignments"),
        "--format", "json", "--dynamic", "--sandbox", "bwrap",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode not in (0, 1):
        raise SystemExit(f"{principle_dir.name}: tool failed\n{completed.stderr[-2000:]}")
    report = json.loads(completed.stdout)
    return {target["display_name"]: target["results"] for target in report["targets"]}


def first_failure(results: list[dict], marker: str | None) -> dict | None:
    for result in results:
        if result["status"] == "FAILED" and (marker is None or marker in result["rule_id"]):
            return result
    return None


def callee_short(callee: str) -> str:
    """``builtins:print`` as ``print()``, ``grades:average`` as ``grades.average()``."""
    return f"{_BARE_CALLEES.get(callee, callee.replace(':', '.'))}()"


def _first_fact(result: dict) -> dict:
    return ((result.get("details") or {}).get("facts") or [{}])[0]


def explanation(error: dict, result: dict) -> str:
    target = result.get("target") or {}
    fact = _first_fact(result)
    values = _Placeholders(
        function=target.get("qualname", "?"),
        file=target.get("file", "?"),
        line=target.get("line", "?"),
        fact_file=fact.get("file") or "?",
        fact_line=fact.get("line") or "?",
        via_last=(fact.get("via") or ["?"])[-1],
        via_first_line=fact.get("origin_line") or "?",
    )
    values.update({key: fact[key] for key in _FACT_KEYS if fact.get(key) is not None})
    if fact.get("callee") is not None:
        values["callee_short"] = callee_short(fact["callee"])
    if fact.get("change") is not None:
        values["change"] = _CHANGE_CS.get(fact["change"], fact["change"])
    what = error["what"].format_map(values)
    why = " ".join(error["why"].split())
    return f"**Co:** {what}\n\n**Proč:** {why}\n\n**Jak opravit:** {error['fix']}"


def signature(result: dict) -> dict[str, Any]:
    """The first fact of a failure, reduced to what tells errors apart: its kind,
    the change of a write, the callee of a call, whether it took a detour, and
    whether the attribute written is private."""
    fact = _first_fact(result)
    found: dict[str, Any] = {key: fact[key] for key in _SIGNATURE_KEYS if fact.get(key) is not None}
    found["via"] = bool(fact.get("via"))
    if fact.get("attribute") is not None:
        found["private"] = str(fact["attribute"]).startswith("_")
    return found


def error_signatures(entry: dict, catalogue: dict[str, list[dict]]) -> dict[str, dict[str, Any]]:
    """Error id -> the signature of its example's failure (``run_catalogue`` results)."""
    found: dict[str, dict[str, Any]] = {}
    for error in entry.get("errors", []):
        if "detected_by" not in error or error["example"] not in catalogue:
            continue
        failure = first_failure(catalogue[error["example"]], error["detected_by"])
        if failure is not None:
            found[error["id"]] = signature(failure)
    return found


def choose_error(entry: dict, result: dict, signatures: dict[str, dict[str, Any]]) -> dict | None:
    """The catalogue error that best explains a failed result, or ``None``.

    Candidates are the errors detected by the failing marker; the one whose
    example's signature shares the most values wins, ties in catalogue order.
    """
    observed = signature(result)
    best: dict | None = None
    best_score = -1
    for error in entry.get("errors", []):
        if "detected_by" not in error or error["detected_by"] not in result["rule_id"]:
            continue
        expected = signatures.get(error["id"], {})
        score = sum(1 for key, value in expected.items() if observed.get(key) == value)
        if score > best_score:
            best, best_score = error, score
    return best
