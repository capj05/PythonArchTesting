"""Score the LLM judges (E3) against the tool on the same variants.

Reads ``key.json`` (what each neutral id is), ``judgments/<run>/*.json``
(one list of verdicts per batch) and the tool's results in
``../architectural_mutants{,_2}/results{,-llm_mutants}.csv``, and writes
``results.md``: per judge run and per tool, how many mutants it flags
(detection; the rest is the false-negative rate) and how many equivalent
rewrites it flags (false-positive rate), by program and set, plus how often
two runs of the same judge disagree (flip rate).

A judge flags a variant when it says ``violates: true``. The tool flags a
mutant when one of the markers of the intent it breaks fails with a violation
(``caught``), an equivalent when any rule fails (``flagged``).

``--whole`` scores the whole-submission run instead (``key-whole.json``,
``judgments-whole/``, ``results-whole.md``). Its E2 solutions have no known
violation; for them the table counts how many each decider flags, with the
tool's verdicts from ``../llm_solutions/results.csv`` (any marker violated,
or the model failing), and lists every one a judge or the tool flags.

Usage, from the repository root::

    python example/llm_judge/score.py [--whole]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent
CSVS = {
    ("program1", "hand"): EXAMPLES / "architectural_mutants" / "results.csv",
    ("program1", "held-out"): EXAMPLES
    / "architectural_mutants"
    / "results-llm_mutants.csv",
    ("program2", "hand"): EXAMPLES / "architectural_mutants_2" / "results.csv",
    ("program2", "held-out"): EXAMPLES
    / "architectural_mutants_2"
    / "results-llm_mutants.csv",
}


def _tool_verdicts() -> dict[tuple[str, str, str], dict[str, bool]]:
    """(program, set, variant id) -> {tool: flags it}."""
    found: dict[tuple[str, str, str], dict[str, bool]] = {}
    for (program, subset), path in CSVS.items():
        with path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                key = (program, subset, row["variant"])
                mutant = row["kind"] == "mutant"
                flag = row["caught"] == "1" if mutant else row["flagged"] == "1"
                found.setdefault(key, {})[row["tool"]] = flag
    for verdicts in found.values():
        verdicts["markers"] = verdicts.get("static", False) or verdicts.get(
            "runtime", False
        )
        verdicts["markers or model"] = verdicts["markers"] or verdicts.get(
            "model", False
        )
    return found


def _solution_verdicts() -> dict[tuple[str, str], dict[str, bool]]:
    """(program, "variant/run") -> {tool: flags it}, for E2's solutions."""
    found: dict[tuple[str, str], dict[str, bool]] = {}
    path = EXAMPLES / "llm_solutions" / "results.csv"
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            markers = bool(row["violated"])
            model = "FAILED" in (row["model_static"], row["model_runtime"])
            found[(row["program"], f"{row['variant']}/{row['run']}")] = {
                "markers": markers,
                "model": model,
                "markers or model": markers or model,
                "import-linter": False,
            }
    return found


def _judgments(folder: str = "judgments") -> dict[str, dict[str, bool]]:
    """run -> {"program/vNNN": violates}."""
    runs: dict[str, dict[str, bool]] = {}
    for run_dir in sorted((HERE / folder).glob("*")):
        verdicts: dict[str, bool] = {}
        for path in sorted(run_dir.glob("*.json")):
            program = path.stem.split("-")[0]
            for item in json.loads(path.read_text(encoding="utf-8")):
                verdicts[f"{program}/{_neutral(item['id'])}"] = bool(item["violates"])
        if verdicts:
            runs[run_dir.name] = verdicts
    return runs


def _neutral(value: str) -> str:
    """A neutral id as written in the key: ``w33`` and ``w033`` are one."""
    letter, digits = value[:1], value[1:]
    return f"{letter}{int(digits):03d}" if digits.isdigit() else value


def _reasons(folder: str) -> dict[tuple[str, str], str]:
    """(run, "program/id") -> the judge's one-sentence reason."""
    found: dict[tuple[str, str], str] = {}
    for run_dir in sorted((HERE / folder).glob("*")):
        for path in sorted(run_dir.glob("*.json")):
            program = path.stem.split("-")[0]
            for item in json.loads(path.read_text(encoding="utf-8")):
                reason = str(item.get("reason") or "").replace("|", "/")
                found[(run_dir.name, f"{program}/{_neutral(item['id'])}")] = reason
    return found


def _rate(hits: int, total: int) -> str:
    return f"{hits}/{total} ({hits / total:.0%})" if total else "-"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--whole", action="store_true")
    args = parser.parse_args()
    suffix = "-whole" if args.whole else ""
    key: dict[str, Any] = json.loads(
        (HERE / f"key{suffix}.json").read_text(encoding="utf-8")
    )
    tools = _tool_verdicts()
    solutions = _solution_verdicts() if args.whole else {}
    judges = _judgments(f"judgments{suffix}")
    deciders: dict[str, dict[str, bool]] = {
        f"judge {run}": verdicts for run, verdicts in judges.items()
    }
    for tool in ("markers", "model", "markers or model", "import-linter"):
        deciders[f"tool: {tool}"] = {
            neutral: (
                solutions.get((item["program"], item["id"]), {}).get(tool, False)
                if item["kind"] == "solution"
                else tools.get((item["program"], item["set"], item["id"]), {}).get(
                    tool, False
                )
            )
            for neutral, item in key.items()
        }
    groups = [
        (program, subset)
        for program in ("program1", "program2")
        for subset in ("hand", "held-out")
    ]
    title = "whole submissions" if args.whole else "diffs"
    lines = [
        f"# LLM judge versus the tool (E3, {title})",
        "",
        "Generated by `score.py`; do not edit by hand. Detection = mutants "
        "flagged (1 - false-negative rate); FP = equivalent rewrites flagged"
        + (
            "; E2 = independently written solutions flagged (no known " "violation)."
            if args.whole
            else "."
        ),
        "",
        "| Decider | Variants judged | Detection (all) | FP (all) | "
        + ("E2 flagged | " if args.whole else "")
        + " | ".join(f"Det. {p} {s} | FP {p} {s}" for p, s in groups)
        + " |",
        "|---|---|---|---|" + ("---|" if args.whole else "") + "---|---|" * len(groups),
    ]
    for name, verdicts in deciders.items():
        judged = [n for n in key if n in verdicts]

        def count(ids: list[str], kind: str) -> tuple[int, int]:
            chosen = [n for n in ids if key[n]["kind"] == kind]
            return sum(1 for n in chosen if verdicts[n]), len(chosen)

        cells = [_rate(*count(judged, "mutant")), _rate(*count(judged, "equivalent"))]
        if args.whole:
            cells.append(_rate(*count(judged, "solution")))
        for program, subset in groups:
            ids = [
                n
                for n in judged
                if key[n]["program"] == program and key[n]["set"] == subset
            ]
            cells += [_rate(*count(ids, "mutant")), _rate(*count(ids, "equivalent"))]
        lines.append(f"| {name} | {len(judged)} | " + " | ".join(cells) + " |")
    runs = sorted(judges)
    if len(runs) > 1:
        lines += [
            "",
            "## Agreement between judge runs",
            "",
            "| Runs | Common | Disagree |",
            "|---|---|---|",
        ]
        for i, first in enumerate(runs):
            for second in runs[i + 1 :]:
                common = set(judges[first]) & set(judges[second])
                differ = sum(1 for n in common if judges[first][n] != judges[second][n])
                lines.append(
                    f"| {first} × {second} | {len(common)} | {_rate(differ, len(common))} |"
                )
    lines += [
        "",
        "## Variants a judge and the tool disagree on",
        "",
        "| Variant | Set | Kind | Operator | Description | Judges flagging | Markers or model |",
        "|---|---|---|---|---|---|---|",
    ]
    for neutral, item in sorted(key.items()):
        flags = [run for run in runs if judges[run].get(neutral)]
        tool = deciders["tool: markers or model"][neutral]
        judged_runs = [run for run in runs if neutral in judges[run]]
        if not judged_runs:
            continue
        majority = len(flags) * 2 > len(judged_runs)
        if majority != tool:
            lines.append(
                f"| {item['program']} {item['id']} | {item['set']} | {item['kind']} | "
                f"{item['operator']} | {item['description']} | "
                f"{', '.join(flags) or '-'} | {'yes' if tool else 'no'} |"
            )
    if args.whole:
        lines += [
            "",
            "## E2 solutions a judge or the tool flags",
            "",
            "| Solution | Judges flagging (reason of the first) | Markers or model |",
            "|---|---|---|",
        ]
        reasons = _reasons(f"judgments{suffix}")
        for neutral, item in sorted(key.items()):
            if item["kind"] != "solution":
                continue
            flags = [run for run in runs if judges[run].get(neutral)]
            tool = deciders["tool: markers or model"][neutral]
            if flags or tool:
                why = reasons.get((flags[0], neutral), "") if flags else ""
                lines.append(
                    f"| {item['program']} {item['id']} ({neutral}) | "
                    f"{', '.join(flags) or '-'}{': ' + why if why else ''} | "
                    f"{'yes' if tool else 'no'} |"
                )
    output = HERE / f"results{suffix}.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
