"""Evaluate simulated student solutions (E2/E6) and write ``results.md``.

Each solution under ``generated/<program>/<variant>/<model>-<run>/solution``
was written by an LLM from ``<program>/assignment.md`` alone (variant
``text``) or with the code skeleton in ``<program>/skeleton`` (variant
``skeleton``). Every solution is checked twice, always with ``--dynamic``
and ``--sandbox bwrap`` (the code is not ours):

- ``markers``: against the program's ``reference/`` with all its markers;
- ``model``: against ``solution/`` + ``model/__init__.py``, the reference as
  the model of the architecture (``architecture_entry`` only);
- ``layered``: the same with ``policy="layered"``, under which an extra
  dependency fails only when it points against the reference's direction.

A ``mapping.json`` next to a solution (assisted pairing, F4.4: pairs an LLM
proposed from ``propose_mapping``) is passed to every check with
``--mapping``; the table counts the pairs applied and refused.

For each run the table gives the markers that failed with a violation, the
ones that found no target (``required_target_missing``: the matching could
not pair the solution with the reference) and the ones that could not run,
and for the model mode the divergent edges per layer and the undecided ones.
There is no ground truth: a violation is a claim to check by hand.

Usage, from the repository root::

    python example/llm_solutions/evaluate.py [--only program1]
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess  # nosec B404 - runs this repository's own CLI
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent
PROGRAMS = {
    "program1": EXAMPLES / "architectural_mutants",
    "program2": EXAMPLES / "architectural_mutants_2",
}
_NOT_RUN = ("case_setup_failed", "reference_failed", "target_kind_mismatch")
_NO_MATCH = "required_target_missing"


def _marker(rule_id: str) -> str:
    parts = rule_id.split("/")
    return parts[1] if len(parts) > 1 else rule_id


def _did_not_run(result: dict[str, Any]) -> bool:
    reason = str((result.get("details") or {}).get("reason") or "")
    return result["status"] == "ERROR" or (
        result["status"] == "FAILED"
        and (reason.startswith("probe_") or reason in _NOT_RUN)
    )


_ASSISTED: dict[str, list[int]] = {}


def _check(
    target: Path,
    reference: Path,
    workdir: Path,
    name: str,
    mapping: Path | None = None,
) -> list[dict[str, Any]]:
    output = workdir / f"report-{name}.json"
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
        "--dynamic",
        "--sandbox",
        "bwrap",
        *(["--mapping", str(mapping)] if mapping is not None else []),
    ]
    completed = subprocess.run(  # nosec B603 - fixed argument list
        command, capture_output=True, text=True, check=False
    )
    if completed.returncode not in (0, 1) or not output.exists():
        raise SystemExit(
            f"the CLI failed on {target} (exit {completed.returncode}):\n"
            f"{completed.stderr[-2000:]}"
        )
    report = json.loads(output.read_text(encoding="utf-8"))
    codes = [
        reason.get("code")
        for t in report["targets"]
        for match in t["matching"]["matches"]
        for reason in match.get("reasons") or []
    ]
    _ASSISTED[f"{target}:{name}"] = [
        codes.count("assisted_mapping"),
        codes.count("assisted_mapping_rejected"),
    ]
    return [r for t in report["targets"] for r in t["results"]]


def _summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    violated: set[str] = set()
    unmatched: set[str] = set()
    not_run: set[str] = set()
    for result in results:
        if result["status"] not in ("FAILED", "ERROR"):
            continue
        reason = (result.get("details") or {}).get("reason")
        if _did_not_run(result):
            not_run.add(_marker(result["rule_id"]))
        elif reason == _NO_MATCH:
            unmatched.add(_marker(result["rule_id"]))
        else:
            violated.add(_marker(result["rule_id"]))
    return {
        "violated": sorted(violated),
        "unmatched": sorted(unmatched),
        "not_run": sorted(not_run),
    }


def _model(results: list[dict[str, Any]]) -> dict[str, Any]:
    divergent: dict[str, list[str]] = {}
    undecided: list[str] = []
    statuses: dict[str, str] = {}
    for result in results:
        if _marker(result["rule_id"]) != "architecture_entry":
            continue
        kind = "runtime" if result["rule_id"].startswith("DYN") else "static"
        details = result.get("details") or {}
        statuses[kind] = (
            "not run"
            if _did_not_run(result)
            else (
                "unmatched"
                if details.get("reason") == _NO_MATCH
                else str(result["status"])
            )
        )
        for layer, diff in (details.get("architecture") or {}).items():
            for edge in diff.get("divergent") or []:
                divergent.setdefault(f"{kind} {layer}", []).append(edge)
        undecided.extend(details.get("undecided") or [])
    return {
        "statuses": statuses,
        "divergent": divergent,
        "undecided": sorted(set(undecided)),
    }


def _model_reference(program: Path, destination: Path, policy: str = "") -> Path:
    shutil.copytree(
        program / "solution", destination, ignore=shutil.ignore_patterns("__pycache__")
    )
    text = (program / "model" / "__init__.py").read_text(encoding="utf-8")
    if policy:
        text = text.replace(
            "architecture_entry(", f'architecture_entry(\n        policy="{policy}",', 1
        )
    (destination / "__init__.py").write_text(text, encoding="utf-8")
    return destination


def _runs(name: str) -> list[tuple[str, str, Path]]:
    root = HERE / "generated" / name
    found = []
    for solution in sorted(root.glob("*/*/solution")):
        found.append((solution.parent.parent.name, solution.parent.name, solution))
    return found


def _cell(items: list[str]) -> str:
    return ", ".join(items) or "-"


def _render(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Simulated student solutions: results",
        "",
        "Generated by `evaluate.py`; do not edit by hand.",
        "",
        "| Program | Variant | Run | Markers violated | No target (pairing) | "
        "Could not run | Model static | Model runtime | Model divergent | "
        "Model undecided | Layered static | Layered runtime | Layered undecided | "
        "Assisted pairs applied / refused |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        markers, model = row["markers"], row["model"]
        divergent = "; ".join(
            f"{layer}: {', '.join(edges)}"
            for layer, edges in sorted(model["divergent"].items())
        )
        lines.append(
            f"| {row['program']} | {row['variant']} | {row['run']} | "
            f"{_cell(markers['violated'])} | {_cell(markers['unmatched'])} | "
            f"{_cell(markers['not_run'])} | {model['statuses'].get('static', '-')} | "
            f"{model['statuses'].get('runtime', '-')} | {divergent or '-'} | "
            f"{len(model['undecided'])} | "
            f"{row['layered']['statuses'].get('static', '-')} | "
            f"{row['layered']['statuses'].get('runtime', '-')} | "
            f"{len(row['layered']['undecided'])} | "
            f"{row['assisted'][0]} / {row['assisted'][1]} |"
        )
    lines += [
        "",
        "## Per variant",
        "",
        "| Program | Variant | Runs | Any marker violated | "
        "Any marker without target | Model failed | Model could not run | "
        "Layered failed |",
        "|---|---|---|---|---|---|---|---|",
    ]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["program"], row["variant"]), []).append(row)
    for (program, variant), group in sorted(groups.items()):
        lines.append(
            f"| {program} | {variant} | {len(group)} | "
            f"{sum(1 for r in group if r['markers']['violated'])} | "
            f"{sum(1 for r in group if r['markers']['unmatched'])} | "
            f"{sum(1 for r in group if 'FAILED' in r['model']['statuses'].values())} | "
            f"{sum(1 for r in group if {'not run', 'ERROR'} & set(r['model']['statuses'].values()))} | "
            f"{sum(1 for r in group if 'FAILED' in r['layered']['statuses'].values())} |"
        )
    return "\n".join(lines) + "\n"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "program",
                "variant",
                "run",
                "violated",
                "unmatched",
                "not_run",
                "model_static",
                "model_runtime",
                "model_divergent",
                "model_undecided",
            ]
        )
        for row in rows:
            model = row["model"]
            writer.writerow(
                [
                    row["program"],
                    row["variant"],
                    row["run"],
                    ";".join(row["markers"]["violated"]),
                    ";".join(row["markers"]["unmatched"]),
                    ";".join(row["markers"]["not_run"]),
                    model["statuses"].get("static", ""),
                    model["statuses"].get("runtime", ""),
                    ";".join(
                        f"{layer}:{edge}"
                        for layer, edges in sorted(model["divergent"].items())
                        for edge in edges
                    ),
                    ";".join(model["undecided"]),
                ]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma-separated program names")
    parser.add_argument(
        "--no-mapping",
        action="store_true",
        help="ignore the solutions' mapping.json (automatic pairing only)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=HERE,
        help="where results.md and results.csv go (default: next to this script)",
    )
    args = parser.parse_args()
    wanted = set(args.only.split(",")) if args.only else set(PROGRAMS)
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="llm-solutions-") as tmp:
        workdir = Path(tmp)
        for name, program in PROGRAMS.items():
            if name not in wanted:
                continue
            model = _model_reference(program, workdir / name / "model" / "reference")
            layered = _model_reference(
                program, workdir / name / "layered" / "reference", "layered"
            )
            for variant, run, solution in _runs(name):
                scratch = workdir / name / variant / run
                scratch.mkdir(parents=True)
                target = scratch / "solution"
                shutil.copytree(
                    solution, target, ignore=shutil.ignore_patterns("__pycache__")
                )
                mapping = solution.parent / "mapping.json"
                mapping_file = (
                    mapping if mapping.is_file() and not args.no_mapping else None
                )
                row = {
                    "program": name,
                    "variant": variant,
                    "run": run,
                    "markers": _summarise(
                        _check(
                            target,
                            program / "reference",
                            scratch,
                            "markers",
                            mapping_file,
                        )
                    ),
                    "model": _model(
                        _check(target, model, scratch, "model", mapping_file)
                    ),
                    "assisted": _ASSISTED.get(f"{target}:markers", [0, 0]),
                    "layered": _model(
                        _check(target, layered, scratch, "layered", mapping_file)
                    ),
                }
                print(
                    f"{name} {variant} {run}: {row['markers']['violated']} "
                    f"model={row['model']['statuses']}",
                    flush=True,
                )
                rows.append(row)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "results.md").write_text(_render(rows), encoding="utf-8")
    _write_csv(args.output_dir / "results.csv", rows)
    print(f"wrote {args.output_dir / 'results.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
