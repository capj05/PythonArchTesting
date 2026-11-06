"""Shared by ``verify.py`` and ``pilot/run_tool.py``: run the tool, explain a failure.

The catalogue entries ship with the tool (``pythonarchtesting.principles``);
``<principle>/principle.toml`` here names its entry by ``id`` and maps each
error and neutral change to its example variant (``[examples]``);
``<principle>/task.toml`` binds the entry's roles to the unannotated
``reference/`` and gives the cases, and the tool runs with the principle
directory itself as ``--source`` (a task, see ``docs/tasks.md``).

The classification and the explanation come from the tool
(``pythonarchtesting.principles.classify``), without any LLM: each fact of a
failed result is matched against the declared ``signature`` of the catalogue
errors of the failing marker (the most specific match wins; none matches: the
failure stays unexplained), and the error's ``what`` is filled from the
target and the fact (the placeholders ``describe_principle`` documents). Here
only the Markdown around ``what`` / ``why`` / ``fix`` is composed.

Needs Python 3.11+ (tomllib); the tool itself supports 3.10.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from pythonarchtesting.principles import (
    Finding,
    classify_result,
    fact_signature,
    fill_what,
    get_principle,
    rule_marker,
)

CLI = Path(sys.executable).with_name("python-arch-test")
# Rule failures that are no verdict on the code: the matching found no target.
NO_MATCH = "required_target_missing"


def load_entry(principle_dir: Path) -> dict[str, Any]:
    """The catalogue entry ``<principle>/principle.toml`` points to, as a dict;
    each error and neutral change also carries its ``example`` variant. The
    task (``task.toml``) must be of the same principle and bind every role of
    the entry."""
    path = principle_dir / "principle.toml"
    pointer = tomllib.loads(path.read_text(encoding="utf-8"))
    entry = get_principle(pointer["id"]).to_dict()
    task_path = principle_dir / "task.toml"
    task = tomllib.loads(task_path.read_text(encoding="utf-8"))
    if task.get("principle") != pointer["id"]:
        raise SystemExit(f"{task_path}: principle must be {pointer['id']!r}")
    if set(task.get("roles", {})) != set(entry["roles"]):
        raise SystemExit(f"{task_path}: [roles] must bind exactly the roles {sorted(entry['roles'])}")
    examples: dict[str, str] = pointer.get("examples", {})
    items = entry["errors"] + entry["neutral"]
    unknown = sorted(set(examples) - {item["id"] for item in items})
    missing = sorted(item["id"] for item in items if item["id"] not in examples)
    if unknown or missing:
        raise SystemExit(f"{path}: [examples] names unknown ids {unknown} and lacks {missing}")
    for item in items:
        item["example"] = examples[item["id"]]
    return entry


def run_catalogue(principle_dir: Path) -> dict[str, list[dict]]:
    """Run the tool over the principle's variants, with the principle's task
    as the source; results per variant name."""
    command = [
        str(CLI),
        "--source", str(principle_dir),
        "--targets-dir", str(principle_dir / "assignments"),
        "--format", "json", "--dynamic", "--sandbox", "bwrap",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode not in (0, 1):
        raise SystemExit(f"{principle_dir.name}: tool failed\n{completed.stderr[-2000:]}")
    report = json.loads(completed.stdout)
    return {target["display_name"]: target["results"] for target in report["targets"]}


def first_failure(results: list[dict], marker: str | None) -> dict | None:
    """The first failed result, of ``marker`` exactly when one is given."""
    for result in results:
        if result["status"] == "FAILED" and (
            marker is None or rule_marker(result["rule_id"]) == marker
        ):
            return result
    return None


def _first_fact(result: dict) -> dict:
    return ((result.get("details") or {}).get("facts") or [{}])[0]


def markdown(what: str, why: str, fix: str) -> str:
    return f"**What:** {what}\n\n**Why:** {why}\n\n**Fix:** {fix}"


def explanation(error: dict, result: dict) -> str:
    """The explanation of a failed result by ``error``, from its first fact."""
    return markdown(fill_what(error["what"], result, _first_fact(result)), error["why"], error["fix"])


def finding_text(finding: Finding) -> str:
    """The explanation of one classified finding; an unclassified one names
    its rule and the violation."""
    if finding.error_id is None:
        return f"**What:** rule `{finding.rule}` failed: {finding.text}"
    return markdown(finding.what or "?", finding.why or "", finding.fix or "")


def findings(entry: dict, result: dict) -> list[Finding]:
    """The findings of a failed result by the catalogue entry's errors."""
    return classify_result(get_principle(entry["id"]), result)


def signature(result: dict) -> dict[str, Any]:
    """The first fact of a failure, reduced like a catalogue error's ``signature``."""
    return fact_signature(_first_fact(result))


def choose_error(entry: dict, result: dict) -> dict | None:
    """The catalogue error (of ``entry``) that explains a failed result's first
    fact, or ``None`` when no typical error does."""
    found = findings(entry, result)
    error_id = found[0].error_id if found else None
    return next((error for error in entry["errors"] if error["id"] == error_id), None)
