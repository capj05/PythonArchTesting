"""Run the architectural-mutant evaluation and write ``results.md``.

Every variant (the unchanged solution, each mutant, each equivalent rewrite)
is copied to a temporary directory, patched, and checked by every tool:

- ``static``: this repository's CLI against ``reference/`` without
  ``--dynamic``, static rules only;
- ``runtime``: the same with ``--dynamic``, runtime rules only;
- ``import-linter``: import-linter with contracts generated from the
  reference's import markers (``baselines/importlinter.py``);
- ``model``: this repository's CLI with ``--dynamic`` against a reference
  made of ``solution/`` and ``model/__init__.py``, which declares nothing but
  ``architecture_entry``: the reference itself is the model (F2).

``--program`` picks another program laid out the same way (``reference/``,
``solution/``, ``mutants.py``); its results go next to it.

A mutant is caught by a tool when one of the markers in its ``detected_by``
fails there with a violation (for import-linter: a contract generated from
such a marker is broken). The results go to a Markdown table and to a CSV
with one row per variant and tool.

Usage, from the repository root::

    python example/architectural_mutants/run.py [--program DIR]
        [--only M01,E02] [--output FILE] [--csv FILE] [--mutants FILE]

``--mutants`` evaluates a held-out set (same shape as ``mutants.py``) and
writes ``results-<file>.md`` / ``.csv``.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import subprocess  # nosec B404 - runs this repository's own CLI
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from baselines import importlinter

HERE = Path(__file__).resolve().parent
PACKAGE = "solution"
TOOLS = ("static", "runtime", "import-linter", "model")
MODEL_MARKER = "architecture_entry"  # the marker the model mode declares
_RUNTIME_PREFIXES = ("DYN", "FLW002")
# A runtime rule that failed for one of these reasons observed nothing.
_NOT_RUN = ("case_setup_failed", "reference_failed", "target_kind_mismatch")
# A rule that failed for this reason found no target entity to check: the
# target is not wrong, the matching did not find the reference's counterpart.
_NO_MATCH = "required_target_missing"


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
    for old, new in (variant.get("renames") or {}).items():
        (root / old).rename(root / new)
    for name in variant.get("removed_files") or []:
        (root / name).unlink()
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


def _apply_error(variant: dict[str, Any], program: Path) -> str | None:
    """Why ``variant`` does not apply to ``program/solution``, or ``None``."""
    with tempfile.TemporaryDirectory(prefix="archmutant-apply-") as tmp:
        target = Path(tmp) / PACKAGE
        shutil.copytree(program / "solution", target)
        try:
            _apply(variant, target)
        except (SystemExit, OSError, ValueError, TypeError, IndexError) as exc:
            # A variant someone else wrote may be malformed; report, do not crash.
            return f"{type(exc).__name__}: {exc}"
        for path in target.rglob("*.py"):
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
            except SyntaxError as exc:
                return f"{path.name} does not compile: {exc}"
    return None


def _check(
    target: Path, reference: Path, dynamic: bool, workdir: Path, name: str = ""
) -> list[dict[str, Any]]:
    label = name or ("dynamic" if dynamic else "static")
    output = workdir / f"report-{label}.json"
    command = [
        sys.executable,
        "-m",
        "pythonarchtesting.cli",
        "--source",
        str(reference),
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


def _no_match(result: dict[str, Any]) -> bool:
    return (result.get("details") or {}).get("reason") == _NO_MATCH


def _ours(failed: list[dict[str, Any]], relevant: set[str]) -> dict[str, Any]:
    markers = sorted({_marker(r["rule_id"]) for r in failed})
    # A rule that found no target says nothing about the variant: not a catch.
    judged = {_marker(r["rule_id"]) for r in failed if not _no_match(r)}
    return {
        "failing": markers,
        # Markers with a verdict: a failure only for want of a target is none.
        "judged": sorted(judged),
        "caught": any(marker in relevant for marker in judged),
        "unmatched": sorted(
            {
                _marker(r["rule_id"])
                for r in failed
                if (r.get("details") or {}).get("reason") == _NO_MATCH
            }
        ),
        "error": "",
    }


def _model_reference(program: Path, destination: Path) -> Path | None:
    """``solution/`` plus ``model/__init__.py``: the reference of the model mode."""
    declaration = program / "model" / "__init__.py"
    if not declaration.is_file():
        return None
    shutil.copytree(program / "solution", destination)
    shutil.copyfile(declaration, destination / "__init__.py")
    return destination


def _model(results: list[dict[str, Any]]) -> dict[str, Any]:
    """The model mode's outcome: any ``architecture_entry`` failure catches."""
    ours = [r for r in results if _marker(r["rule_id"]) == MODEL_MARKER]
    failed = [r for r in ours if r["status"] == "FAILED" and not _did_not_run(r)]
    failing = sorted(
        f"{MODEL_MARKER} ({'runtime' if _is_runtime(r['rule_id']) else 'static'})"
        for r in failed
    )
    return {
        "failing": failing,
        "judged": sorted(
            f"{MODEL_MARKER} ({'runtime' if _is_runtime(r['rule_id']) else 'static'})"
            for r in failed
            if not _no_match(r)
        ),
        "caught": any(not _no_match(r) for r in failed),
        "unmatched": sorted(
            {
                _marker(r["rule_id"])
                for r in failed
                if (r.get("details") or {}).get("reason") == _NO_MATCH
            }
        ),
        "error": "; ".join(
            f"{r['rule_id']}: {(r.get('details') or {}).get('summary', '')}"
            for r in ours
            if _did_not_run(r)
        ),
        "undecided": sorted(
            item
            for r in ours
            if r["status"] == "OK"
            for item in (r.get("details") or {}).get("undecided") or []
        ),
    }


def _evaluate(
    variant: dict[str, Any],
    program: Path,
    contracts: Path,
    model: Path | None = None,
    reference: Path | None = None,
) -> dict[str, Any]:
    relevant = set(variant.get("detected_by") or [])
    with tempfile.TemporaryDirectory(prefix="archmutant-") as tmp:
        workdir = Path(tmp)
        target = workdir / PACKAGE
        shutil.copytree(program / "solution", target)
        _apply(variant, target)
        reference = reference or program / "reference"
        static = _check(target, reference, dynamic=False, workdir=workdir)
        dynamic = _check(target, reference, dynamic=True, workdir=workdir)
        broken, error = importlinter.check(target, contracts)
        modelled = (
            _check(target, model, dynamic=True, workdir=workdir, name="model")
            if model is not None
            else None
        )
    crashed = [
        _marker(result["rule_id"])
        for result in dynamic
        if _is_runtime(result["rule_id"]) and _did_not_run(result)
    ]
    tools = {
        "static": _ours(_failures(static, runtime=False), relevant),
        "runtime": _ours(_failures(dynamic, runtime=True), relevant),
        "import-linter": {
            "failing": broken,
            "judged": broken,
            "caught": any(
                importlinter.contract_marker(name) in relevant for name in broken
            ),
            "unmatched": [],
            "error": error,
        },
        "model": (
            _model(modelled)
            if modelled is not None
            else {
                "failing": [],
                "judged": [],
                "caught": False,
                "unmatched": [],
                "error": "no model",
            }
        ),
    }
    return {
        **{key: variant[key] for key in ("id", "operator", "description")},
        "tools": tools,
        "crashed": sorted(set(crashed)),
        "unexercised": _unexercised(dynamic),
    }


def _mark(outcome: dict[str, Any]) -> str:
    if outcome["error"]:
        return "error"
    return "yes" if outcome["caught"] else "no"


def _ours_failing(row: dict[str, Any]) -> list[str]:
    """Failing markers of either kind; a marker with both parts counts once."""
    return sorted(
        set(row["tools"]["static"]["failing"] + row["tools"]["runtime"]["failing"])
    )


def _count(group: list[dict[str, Any]], test: Callable[[dict[str, Any]], bool]) -> int:
    return sum(1 for row in group if test(row["tools"]))


def _render(baseline: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    mutants = [row for row in rows if row["id"].startswith("M")]
    equivalents = [row for row in rows if row["id"].startswith("E")]
    base = baseline["tools"]
    lines = [
        "# Architectural mutants: results",
        "",
        "Generated by `run.py`; do not edit by hand.",
        "",
        "Unchanged solution: "
        + ", ".join(
            f"{tool} failures {base[tool]['failing'] or base[tool]['error'] or 'none'}"
            for tool in TOOLS
        )
        + ".",
        "",
        "## Mutants",
        "",
        "| Mutant | Operator | Seeded violation | Static | Runtime | import-linter | "
        "Model | Failing markers | Lines no case ran (survivors only) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in mutants:
        tools = row["tools"]
        failing = ", ".join(_ours_failing(row)) or "-"
        # What the cases left out explains a survivor; on a caught mutant it
        # is noise.
        not_run = "-" if tools["runtime"]["caught"] else "; ".join(row["unexercised"])
        lines.append(
            f"| {row['id']} | {row['operator']} | {row['description']} | "
            f"{_mark(tools['static'])} | {_mark(tools['runtime'])} | "
            f"{_mark(tools['import-linter'])} | {_mark(tools['model'])} | "
            f"{failing} | {not_run or '-'} |"
        )
    lines += [
        "",
        "## Caught per operator",
        "",
        "| Operator | Mutants | Static | Runtime | Static or runtime | "
        "Static only | Runtime only | import-linter | Model |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in mutants:
        groups.setdefault(row["operator"], []).append(row)
    groups["all"] = mutants
    for operator, group in groups.items():
        counts = [
            _count(group, lambda t: t["static"]["caught"]),
            _count(group, lambda t: t["runtime"]["caught"]),
            _count(group, lambda t: t["static"]["caught"] or t["runtime"]["caught"]),
            _count(
                group, lambda t: t["static"]["caught"] and not t["runtime"]["caught"]
            ),
            _count(
                group, lambda t: t["runtime"]["caught"] and not t["static"]["caught"]
            ),
            _count(group, lambda t: t["import-linter"]["caught"]),
            _count(group, lambda t: t["model"]["caught"]),
        ]
        name = f"**{operator}**" if operator == "all" else operator
        lines.append(
            f"| {name} | {len(group)} | " + " | ".join(map(str, counts)) + " |"
        )
    lines += [
        "",
        "## Equivalent rewrites (false positives)",
        "",
        "| Variant | Rewrite | Failing markers | Of them, no matching target | "
        "Runtime rules that could not run | import-linter | Model | "
        "Model: undecided |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in equivalents:
        tools = row["tools"]
        failing = ", ".join(_ours_failing(row)) or "none"
        unmatched = (
            ", ".join(tools["static"]["unmatched"] + tools["runtime"]["unmatched"])
            or "-"
        )
        linter = tools["import-linter"]
        flagged = "error" if linter["error"] else ", ".join(linter["failing"]) or "none"
        model = tools["model"]
        modelled = "error" if model["error"] else ", ".join(model["failing"]) or "none"
        undecided = "; ".join(model.get("undecided") or []) or "-"
        lines.append(
            f"| {row['id']} | {row['description']} | {failing} | {unmatched} | "
            f"{', '.join(row['crashed']) or '-'} | {flagged} | {modelled} | "
            f"{undecided} |"
        )
    # For equivalents the table above names them already.
    crashed = [row for row in mutants if row["crashed"]]
    if crashed:
        lines += ["", "## Mutants with runtime rules that could not run", ""]
        lines += [f"- {row['id']}: {', '.join(row['crashed'])}" for row in crashed]
    model_errors = [row for row in rows if row["tools"]["model"]["error"]]
    if model_errors:
        lines += ["", "## Model rules that could not run", ""]
        lines += [
            f"- {row['id']}: {row['tools']['model']['error']}" for row in model_errors
        ]
    errors = [row for row in rows if row["tools"]["import-linter"]["error"]]
    if errors:
        lines += ["", "## import-linter errors", ""]
        lines += [
            f"- {row['id']}: {_last_message(row['tools']['import-linter']['error'])}"
            for row in errors
        ]
    return "\n".join(lines) + "\n"


def _last_message(text: str) -> str:
    """The last paragraph of an error output, its wrapped lines joined."""
    paragraphs = [part for part in text.strip().split("\n\n") if part.strip()]
    return " ".join(paragraphs[-1].split()) if paragraphs else ""


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """One row per variant and tool; ``caught`` is empty for equivalents.

    ``flagged``: some rule failed with a verdict (``judged``); a rule that
    failed only for want of a matching target judged nothing, as in E2 and E4.
    """
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "variant",
                "kind",
                "operator",
                "tool",
                "flagged",
                "caught",
                "failing",
                "judged",
                "unmatched",
                "error",
            ]
        )
        for row in rows:
            mutant = row["id"].startswith("M")
            for tool in TOOLS:
                outcome = row["tools"][tool]
                writer.writerow(
                    [
                        row["id"],
                        "mutant" if mutant else "equivalent",
                        row["operator"],
                        tool,
                        int(bool(outcome["judged"])),
                        int(outcome["caught"]) if mutant else "",
                        ";".join(outcome["failing"]),
                        ";".join(outcome["judged"]),
                        ";".join(outcome["unmatched"]),
                        outcome["error"].splitlines()[-1] if outcome["error"] else "",
                    ]
                )


def _variants(program: Path, mutants: Path | None = None) -> list[dict[str, Any]]:
    """The mutants and equivalent rewrites of ``program/mutants.py``.

    ``mutants`` names another file of the same shape instead, such as a
    held-out set someone else wrote.
    """
    path = mutants or program / "mutants.py"
    spec = importlib.util.spec_from_file_location(f"mutants_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"no {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.MUTANTS) + list(module.EQUIVALENTS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--program", type=Path, default=HERE)
    parser.add_argument("--only", help="comma-separated variant ids")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument(
        "--reference",
        type=Path,
        help="evaluate this reference instead of the program's reference/ "
        "(for example one an LLM wrote markers into)",
    )
    parser.add_argument(
        "--mutants",
        type=Path,
        help="variants from this file instead of mutants.py; those that do "
        "not apply are reported and left out",
    )
    args = parser.parse_args()
    program = args.program.resolve()
    # A held-out set gets its own results next to the program's.
    suffix = f"-{args.mutants.stem}" if args.mutants is not None else ""
    output = args.output or program / f"results{suffix}.md"
    csv_path = args.csv or program / f"results{suffix}.csv"
    variants = _variants(program, args.mutants)
    invalid: list[tuple[str, str]] = []
    if args.mutants is not None:
        valid = []
        for variant in variants:
            error = _apply_error(variant, program)
            if error is None:
                valid.append(variant)
            else:
                invalid.append((variant["id"], error.splitlines()[0]))
        variants = valid
    if args.only:
        wanted = set(args.only.split(","))
        variants = [variant for variant in variants if variant["id"] in wanted]
    reference = (args.reference or program / "reference").resolve()
    with tempfile.TemporaryDirectory(prefix="archmutant-contracts-") as tmp:
        contracts = Path(tmp) / ".importlinter"
        contracts.write_text(
            importlinter.contracts(reference, PACKAGE),
            encoding="utf-8",
        )
        model = _model_reference(program, Path(tmp) / "model" / "reference")
        baseline = _evaluate(
            {"id": "base", "operator": "-", "description": "-"},
            program,
            contracts,
            model,
            reference,
        )
        rows = []
        for variant in variants:
            row = _evaluate(variant, program, contracts, model, reference)
            print(
                f"{row['id']}: "
                + " ".join(f"{tool}={_mark(row['tools'][tool])}" for tool in TOOLS)
                + f" failing={_ours_failing(row)}",
                flush=True,
            )
            rows.append(row)
    rendered = _render(baseline, rows)
    if invalid:
        rendered += "\n## Variants that did not apply\n\n" + "".join(
            f"- {variant_id}: {error}\n" for variant_id, error in invalid
        )
    output.write_text(rendered, encoding="utf-8")
    _write_csv(csv_path, rows)
    print(f"wrote {output} and {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
