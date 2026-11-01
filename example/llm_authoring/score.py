"""Score the markers the E4 agents wrote, on the hand-written mutants.

Each ``<program>/<condition>-<run>/reference`` is a copy of the correct
solution into which an agent wrote markers for the assignment's graded
architecture: condition A with ``validate`` and ``evaluate`` only, condition B
also with ``check-cases`` and ``verify-marker`` (``tools.py``). For each one
this script counts the rules it compiles to and the invalid declarations, and
runs the architectural-mutant harness with it as the reference (all
hand-written mutants and equivalent rewrites of the program). A mutant is
*caught* when one of the markers of the intent it breaks fails (the
harness's criterion), *flagged* when any rule fails with a violation; an
equivalent rewrite that is flagged is a false positive. The authors' own
reference (``reference/`` of the program) is scored the same way, for scale.

Usage, from the repository root::

    python example/llm_authoring/score.py
"""

from __future__ import annotations

import csv
import subprocess  # nosec B404 - runs this repository's own harness
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
RUN = EXAMPLES / "architectural_mutants" / "run.py"
# Runs 1-2 of each condition are the first measurement (2026-10-31); runs 3-6
# of program 1 the second (2026-11-01, N = 4 per condition, after the faster
# verify_marker and the operators for module interfaces and ports).
SECOND_MEASUREMENT = 3


def _rules(reference: Path) -> tuple[int, int]:
    """Rules compiled from ``reference`` and invalid declarations among them."""
    from pythonarchtesting.config import load_config
    from pythonarchtesting.runner.source_prep import prepare_source

    state = prepare_source(
        config=load_config(cli_args={}, discover_from_cwd=False), source_path=reference
    )
    invalid = sum(1 for rule in state.rules if "invalid" in rule.rule_id)
    return len(state.rules) - invalid, invalid + len(state.compiler_validations)


def _harness(program: Path, reference: Path, workdir: Path) -> dict[str, Any]:
    output, table = workdir / "results.md", workdir / "results.csv"
    completed = subprocess.run(  # nosec B603 - fixed argument list
        [
            sys.executable,
            str(RUN),
            "--program",
            str(program),
            "--reference",
            str(reference),
            "--output",
            str(output),
            "--csv",
            str(table),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return {"error": completed.stderr[-500:]}
    baseline = next(
        line
        for line in output.read_text(encoding="utf-8").splitlines()
        if line.startswith("Unchanged solution")
    )
    rows: dict[str, dict[str, Any]] = {}
    with table.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["tool"] not in ("static", "runtime"):
                continue
            entry = rows.setdefault(
                row["variant"], {"kind": row["kind"], "caught": False, "flagged": False}
            )
            entry["caught"] |= row["caught"] == "1"
            # ``judged``: markers with a rule that failed with a verdict (a rule
            # that found no target judged nothing), per rule, from run.py.
            entry["flagged"] |= bool(row["judged"])
    per_variant = {variant: entry["flagged"] for variant, entry in sorted(rows.items())}
    mutants = [r for r in rows.values() if r["kind"] == "mutant"]
    equivalents = [r for r in rows.values() if r["kind"] == "equivalent"]
    clean = "static failures none, runtime failures none" in baseline
    return {
        "reference_passes": clean,
        "caught": sum(r["caught"] for r in mutants),
        "flagged": sum(r["flagged"] for r in mutants),
        "mutants": len(mutants),
        "fp": sum(r["flagged"] for r in equivalents),
        "equivalents": len(equivalents),
        "per_variant": per_variant,
    }


def _measurement(run: str) -> str | None:
    """``first`` or ``second`` for a run label ``<condition>-<n>``."""
    condition, _, number = run.partition("-")
    if condition not in ("A", "B") or not number.isdigit():
        return None
    return "second" if int(number) >= SECOND_MEASUREMENT else "first"


def _summary(rows: list[dict[str, Any]]) -> list[str]:
    """Mean and range of the mutants caught and flagged and of the FP, per
    program, measurement and condition."""
    lines = [
        "",
        "## Per condition",
        "",
        "Mean (min-max) over the runs of one measurement.",
        "",
        "| Program | Measurement | Condition | Runs | Caught | Flagged | FP |",
        "|---|---|---|---|---|---|---|",
    ]
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        measurement = _measurement(row["run"])
        if measurement and "per_variant" in row:
            key = (row["program"], measurement, row["run"][0])
            groups.setdefault(key, []).append(row)
    for (program, measurement, condition), runs in sorted(groups.items()):
        cells = []
        for field in ("caught", "flagged", "fp"):
            values = [run[field] for run in runs]
            cells.append(
                f"{sum(values) / len(values):.2f} ({min(values)}-{max(values)})"
            )
        lines.append(
            f"| {program} | {measurement} | {condition} | {len(runs)} | "
            + " | ".join(cells)
            + " |"
        )
    return lines


def main() -> int:
    rows = []
    for name, program in PROGRAMS.items():
        runs = [("authors' reference", program / "reference")] + [
            (path.parent.name, path)
            for path in sorted((HERE / name).glob("*/reference"))
        ]
        for label, reference in runs:
            with tempfile.TemporaryDirectory(prefix="e4-") as tmp:
                compiled, invalid = _rules(reference)
                scored = _harness(program, reference, Path(tmp))
            rows.append(
                {
                    "program": name,
                    "run": label,
                    "rules": compiled,
                    "invalid": invalid,
                    **scored,
                }
            )
            print({k: v for k, v in rows[-1].items() if k != "per_variant"}, flush=True)
    lines = [
        "# Markers written by an LLM, with and without the checking tools (E4)",
        "",
        "Generated by `score.py`; do not edit by hand. A = validate + evaluate "
        "only; B = also check-cases + verify-marker.",
        "",
        "| Program | Run | Rules | Invalid | Reference passes | Mutants caught "
        "(intent's markers) | Mutants flagged (any rule) | FP on equivalents |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        if "error" in row:
            lines.append(
                f"| {row['program']} | {row['run']} | {row['rules']} | "
                f"{row['invalid']} | error | - | - | - |"
            )
            continue
        lines.append(
            f"| {row['program']} | {row['run']} | {row['rules']} | {row['invalid']} | "
            f"{'yes' if row['reference_passes'] else 'no'} | "
            f"{row['caught']}/{row['mutants']} | {row['flagged']}/{row['mutants']} | "
            f"{row['fp']}/{row['equivalents']} |"
        )
    lines += _summary(rows)
    lines += [
        "",
        "## Variants where the runs differ",
        "",
        "A mutant listed with the runs that miss it (no rule flags it), an "
        "equivalent with the runs that flag it.",
        "",
        "| Program | Variant | Runs that get it wrong |",
        "|---|---|---|",
    ]
    for name in PROGRAMS:
        scored = [r for r in rows if r["program"] == name and "per_variant" in r]
        variants = sorted({v for r in scored for v in r["per_variant"]})
        for variant in variants:
            mutant = variant.startswith("M")
            wrong = [
                r["run"]
                for r in scored
                if r["per_variant"].get(variant) is (not mutant)
            ]
            if wrong:
                lines.append(f"| {name} | {variant} | {', '.join(wrong)} |")
    (HERE / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {HERE / 'results.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
