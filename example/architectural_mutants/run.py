"""Run the architectural-mutant evaluation and write ``results.md``.

Every variant (the unchanged solution, each mutant, each equivalent rewrite)
is copied to a temporary directory, patched, and checked against
``reference/`` twice: without ``--dynamic`` (static rules only) and with it
(static and runtime rules). A mutant is caught by static or by runtime rules
when one of the markers in its ``detected_by`` fails there with a violation.

Usage, from the repository root::

    python example/architectural_mutants/run.py [--only M01,E02] [--output FILE]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # nosec B404 - runs this repository's own CLI
import sys
import tempfile
from pathlib import Path
from typing import Any

from mutants import EQUIVALENTS, MUTANTS

HERE = Path(__file__).resolve().parent
REFERENCE = HERE / "reference"
SOLUTION = HERE / "solution"
_RUNTIME_PREFIXES = ("DYN", "FLW002")
# A runtime rule that failed for one of these reasons observed nothing.
_NOT_RUN = ("case_setup_failed", "reference_failed", "target_kind_mismatch")


def _did_not_run(result: dict[str, Any]) -> bool:
    reason = str((result.get("details") or {}).get("reason") or "")
    return result["status"] == "ERROR" or (
        result["status"] == "FAILED"
        and (reason.startswith("probe_") or reason in _NOT_RUN)
    )


def _marker(rule_id: str) -> str:
    """``DYN001/forbid_runtime_calls/v1`` -> ``forbid_runtime_calls``."""
    parts = rule_id.split("/")
    return parts[1] if len(parts) > 1 else rule_id


def _is_runtime(rule_id: str) -> bool:
    return rule_id.startswith(_RUNTIME_PREFIXES)


def _apply(variant: dict[str, Any], root: Path) -> None:
    for name, text in (variant.get("new_files") or {}).items():
        (root / name).write_text(text, encoding="utf-8")
    for name, old, new in variant.get("patches", []):
        path = root / name
        source = path.read_text(encoding="utf-8")
        count = source.count(old)
        if count != 1:
            raise SystemExit(
                f"{variant['id']}: expected the text once in {name}, found {count}:\n"
                f"{old}"
            )
        path.write_text(source.replace(old, new), encoding="utf-8")


def _check(target: Path, dynamic: bool, workdir: Path) -> list[dict[str, Any]]:
    output = workdir / f"report-{'dynamic' if dynamic else 'static'}.json"
    command = [
        sys.executable,
        "-m",
        "pythonarchtesting.cli",
        "--source",
        str(REFERENCE),
        "--target",
        str(target),
        "--format",
        "json",
        "--output",
        str(output),
    ]
    if dynamic:
        command.append("--dynamic")
    completed = subprocess.run(  # nosec B603 - fixed argument list
        command, capture_output=True, text=True, check=False
    )
    if completed.returncode not in (0, 1) or not output.exists():
        raise SystemExit(
            f"the CLI failed on {target} (exit {completed.returncode}):\n"
            f"{completed.stderr[-2000:]}"
        )
    report = json.loads(output.read_text(encoding="utf-8"))
    return [result for target in report["targets"] for result in target["results"]]


def _failures(results: list[dict[str, Any]], runtime: bool) -> list[dict[str, Any]]:
    """Rules of one kind that failed because of a violation, not a crash."""
    failed = []
    for result in results:
        if result["status"] != "FAILED" or _is_runtime(result["rule_id"]) != runtime:
            continue
        if not _did_not_run(result):
            failed.append(result)
    return failed


def _unexercised(results: list[dict[str, Any]]) -> list[str]:
    notes = []
    for result in results:
        coverage = (result.get("details") or {}).get("coverage") or {}
        if coverage.get("unexercised_lines"):
            notes.append(
                f"{_marker(result['rule_id'])}: lines "
                f"{coverage['unexercised_lines']} of {coverage['file']} not run"
            )
    return sorted(set(notes))


def _evaluate(variant: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="archmutant-") as tmp:
        workdir = Path(tmp)
        target = workdir / "solution"
        shutil.copytree(SOLUTION, target)
        _apply(variant, target)
        static = _check(target, dynamic=False, workdir=workdir)
        dynamic = _check(target, dynamic=True, workdir=workdir)
    static_failed = _failures(static, runtime=False)
    runtime_failed = _failures(dynamic, runtime=True)
    relevant = set(variant.get("detected_by") or [])
    crashed = [
        _marker(result["rule_id"])
        for result in dynamic
        if _is_runtime(result["rule_id"]) and _did_not_run(result)
    ]
    return {
        **{key: variant[key] for key in ("id", "operator", "description")},
        "static": sorted({_marker(r["rule_id"]) for r in static_failed}),
        "runtime": sorted({_marker(r["rule_id"]) for r in runtime_failed}),
        "static_caught": any(_marker(r["rule_id"]) in relevant for r in static_failed),
        "runtime_caught": any(
            _marker(r["rule_id"]) in relevant for r in runtime_failed
        ),
        "crashed": sorted(set(crashed)),
        "unexercised": _unexercised(dynamic),
    }


def _mark(flag: bool) -> str:
    return "yes" if flag else "no"


def _render(baseline: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    mutants = [row for row in rows if row["id"].startswith("M")]
    equivalents = [row for row in rows if row["id"].startswith("E")]
    lines = [
        "# Architectural mutants: results",
        "",
        "Generated by `run.py`; do not edit by hand.",
        "",
        f"Unchanged solution: static failures {baseline['static'] or 'none'}, "
        f"runtime failures {baseline['runtime'] or 'none'}.",
        "",
        "## Mutants",
        "",
        "| Mutant | Operator | Seeded violation | Static | Runtime | "
        "Failing markers | Lines no case ran (survivors only) |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in mutants:
        failing = ", ".join(row["static"] + row["runtime"]) or "-"
        # What the cases left out explains a survivor; on a caught mutant it
        # is noise.
        not_run = "-" if row["runtime_caught"] else "; ".join(row["unexercised"])
        lines.append(
            f"| {row['id']} | {row['operator']} | {row['description']} | "
            f"{_mark(row['static_caught'])} | {_mark(row['runtime_caught'])} | "
            f"{failing} | {not_run or '-'} |"
        )
    lines += [
        "",
        "## Caught per operator",
        "",
        "| Operator | Mutants | Static | Runtime | Either | Static only | "
        "Runtime only |",
        "|---|---|---|---|---|---|---|",
    ]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in mutants:
        groups.setdefault(row["operator"], []).append(row)
    groups["all"] = mutants
    for operator, group in groups.items():
        static = sum(row["static_caught"] for row in group)
        runtime = sum(row["runtime_caught"] for row in group)
        either = sum(row["static_caught"] or row["runtime_caught"] for row in group)
        static_only = sum(
            row["static_caught"] and not row["runtime_caught"] for row in group
        )
        runtime_only = sum(
            row["runtime_caught"] and not row["static_caught"] for row in group
        )
        name = f"**{operator}**" if operator == "all" else operator
        lines.append(
            f"| {name} | {len(group)} | {static} | {runtime} | {either} | "
            f"{static_only} | {runtime_only} |"
        )
    lines += [
        "",
        "## Equivalent rewrites (false positives)",
        "",
        "| Variant | Rewrite | Failing markers |",
        "|---|---|---|",
    ]
    for row in equivalents:
        failing = ", ".join(row["static"] + row["runtime"]) or "none"
        lines.append(f"| {row['id']} | {row['description']} | {failing} |")
    crashed = [row for row in rows if row["crashed"]]
    if crashed:
        lines += ["", "## Runtime rules that could not run", ""]
        lines += [f"- {row['id']}: {', '.join(row['crashed'])}" for row in crashed]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma-separated variant ids")
    parser.add_argument("--output", type=Path, default=HERE / "results.md")
    args = parser.parse_args()
    variants = MUTANTS + EQUIVALENTS
    if args.only:
        wanted = set(args.only.split(","))
        variants = [variant for variant in variants if variant["id"] in wanted]
    baseline = _evaluate({"id": "base", "operator": "-", "description": "-"})
    rows = []
    for variant in variants:
        row = _evaluate(variant)
        print(
            f"{row['id']}: static={_mark(row['static_caught'])} "
            f"runtime={_mark(row['runtime_caught'])} "
            f"failing={row['static'] + row['runtime']}",
            flush=True,
        )
        rows.append(row)
    args.output.write_text(_render(baseline, rows), encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
