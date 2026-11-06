"""Score the M6 evaluation: agents' tasks (VO3), explanations (VO5), realistic code.

Writes ``results-vo3-vo5.md`` and ``results-vo3-vo5.csv`` into the M6
directory (``--base``, by default the one of this file):

- **VO3**, per principle, one row for the principle's own task (``example``)
  and one per agent's task (``run-N``, ``results/tasks/<p>/run-N/task.toml``
  beside a copy of the unannotated reference): ``accepted`` and the number of
  ``problems`` of ``prepare_task``, whether the ``task.toml`` is the
  example's (``copied example``: the same TOML data), then the tool with that
  task on the pilot's
  data (``<pilot>/<p>/key.json``: every injected error, every injected neutral
  defect, every carrier): errors flagged x/N, flagged as the injected error
  x/N, defects flagged (false positives) x/N, carriers flagged x/N, and over
  all of them unmatched (failed only for a missing required entity, no verdict
  on the principle, as the pilot's ``UNMATCHED``) and not judged. Flagged = the
  verdict ``failed`` with a violation other than a missing entity. A task the
  tool cannot run reads "not evaluated" with the reason.
- **VO5**, one row per rated explanation (``results/ratings/<p>/<s>.json``
  beside ``results/explanations/<p>/<s>.md`` and its ``<s>.json``):
  location, principle, reason (0-2 each) and their sum, the explainer's and
  the rater's model (``same model`` flags a rating by the explainer's own
  model), the means, and the explanations marked for the owner's review: per
  principle the first ``--review`` (3) in an order seeded by 7.
- **Realistic code**, one row per solution (``data/solutions/<p>/<s>/``, with
  ``data/meta/<p>/<s>.json``): absolute imports asked for, ``__init__.py``
  present, and ``class_overview`` of the principle's own task (verdict, error
  ids, reasons not judged); then one column per judge run
  (``results/judgments/<run>/<p>.json``), at least one.

Exits 1, writing nothing, when an input is missing (a principle's run below
``--runs``, a principle with fewer than ``--explanations`` explanations, fewer
than ``--solutions`` solutions, an explanation without a rating or the other
way round, an explainer's or rater's model, a solution without its meta file,
no judge run, a judge run without a verdict on some solution or principle,
the pilot's data) or malformed, or when a cell of the tables would be empty. The tool runs with ``--dynamic`` under ``bwrap``.

Usage, from the repository root::

    python example/principles/m6/score.py [--runs 3] [--explanations 6]
        [--solutions 6] [--review 3] [--base DIR] [--pilot DIR]
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402
from harness import PILOT, PRINCIPLES, RATING_KEYS, copy_code, read_json  # noqa: E402

SEED = 7
OUTPUT = "results-vo3-vo5"
_EMPTY = re.compile(r"\|\s*(–|-)?\s*(?=\|)")
_RUN_DIR = re.compile(r"^run-(\d+)$")


class Missing(Exception):
    """A required input is missing or malformed."""


def _cell(value: Any) -> str:
    return " ".join(str(value).split()).replace("|", "/")


def _rate(hits: int, total: int) -> str:
    return f"{hits}/{total}"


def _table(header: list[str], rows: list[list[Any]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows),
    ]


def _counts(pool: dict[str, dict[str, Any]], rows: dict[str, dict[str, Any]]) -> dict[str, str]:
    def chosen(kind: str) -> list[str]:
        return [name for name, item in pool.items() if item["kind"] == kind]

    def flagged(names: list[str]) -> int:
        return sum(1 for name in names if harness.failed_by_violation(rows[name]))

    errors = chosen("err")
    right = sum(1 for name in errors if pool[name]["id"] in rows[name]["errors"])
    return {
        "errors flagged": _rate(flagged(errors), len(errors)),
        "as the injected error": _rate(right, len(errors)),
        "defects flagged (FP)": _rate(flagged(chosen("neutral")), len(chosen("neutral"))),
        "carriers flagged": _rate(flagged(chosen("carrier")), len(chosen("carrier"))),
        "unmatched": _rate(sum(1 for name in pool if harness.unmatched(rows[name])), len(pool)),
        "not judged": _rate(sum(1 for name in pool if rows[name]["verdict"] == "not_judged"), len(pool)),
    }


def _runs(base: Path, principle: str, wanted: int) -> dict[int, Path]:
    folder = base / "results" / "tasks" / principle
    found = {
        int(match.group(1)): path / "task.toml"
        for path in sorted(folder.glob("run-*"))
        if (match := _RUN_DIR.match(path.name)) and (path / "task.toml").is_file()
    }
    missing = [n for n in range(1, wanted + 1) if n not in found]
    if missing:
        raise Missing(f"{folder}: no task.toml of run {', '.join(map(str, missing))}")
    return dict(sorted(found.items()))


def _copied(task: Path, example_data: dict[str, Any]) -> str:
    """``yes`` when the task's ``task.toml`` holds the example's TOML data."""
    try:
        data = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return "no"
    return "yes" if data == example_data else "no"


def vo3(base: Path, pilot: Path, runs: int, tmp: Path) -> tuple[list[str], list[dict[str, Any]]]:
    from pythonarchtesting.mcp_server import tasks
    from pythonarchtesting.mcp_server.errors import ToolInputError

    measures = ["errors flagged", "as the injected error", "defects flagged (FP)",
                "carriers flagged", "unmatched", "not judged"]
    header = ["Principle", "Task", "accepted", "problems", "copied example", *measures]
    rows: list[list[Any]] = []
    csv_rows: list[dict[str, Any]] = []
    notes: list[str] = []
    for principle in PRINCIPLES:
        found = _runs(base, principle, runs)
        try:
            pool = harness.build_pool(pilot, principle, tmp / "pool" / principle)
        except SystemExit as error:
            raise Missing(str(error)) from error
        example = harness.example_task(principle)
        example_data = tomllib.loads((example / "task.toml").read_text(encoding="utf-8"))
        decks: dict[str, Path] = {"example": example}
        for number, toml in found.items():
            task = tmp / "tasks" / principle / f"run-{number}"
            copy_code(example / "reference", task / "reference")
            (task / "task.toml").write_bytes(toml.read_bytes())
            decks[f"run-{number}"] = task
        for label, task in decks.items():
            try:
                prepared = tasks.prepare_task(str(task.resolve()))
            except ToolInputError as error:
                values: dict[str, Any] = {"accepted": "no", "problems": f"refused: {error}"}
            else:
                values = {
                    "accepted": "yes" if prepared["accepted"] else "no",
                    "problems": len(prepared["problems"]),
                }
            values["copied example"] = "n/a" if label == "example" else _copied(task, example_data)
            try:
                _, verdicts = harness.evaluate(task, tmp / "pool" / principle, tmp / "reports" / principle / label)
            except ToolInputError as error:
                values.update({m: "not evaluated" for m in measures})
                notes.append(f"- `{principle}` {label}: not evaluated: {_cell(error)}")
            else:
                missing = sorted(set(pool) - set(verdicts))
                if missing:
                    raise Missing(f"{principle} {label}: the report has no {missing}")
                values.update(_counts(pool, verdicts))
            rows.append([f"`{principle}`", label, *values.values()])
            csv_rows += [
                {"section": "VO3", "principle": principle, "item": label, "measure": key, "value": value}
                for key, value in values.items()
            ]
    return _table(header, rows) + (["", *notes] if notes else []), csv_rows


def vo5(base: Path, wanted: int, review: int) -> tuple[list[str], list[dict[str, Any]]]:
    explanations = {
        f"{path.parent.name}/{path.stem}": path
        for path in sorted((base / "results" / "explanations").glob("*/*.md"))
    }
    ratings = {
        f"{path.parent.name}/{path.stem}": path
        for path in sorted((base / "results" / "ratings").glob("*/*.json"))
    }
    problems = [f"{name}: an explanation without a rating" for name in sorted(set(explanations) - set(ratings))]
    problems += [f"{name}: a rating without an explanation" for name in sorted(set(ratings) - set(explanations))]
    problems += [problem for path in ratings.values() for problem in harness.rating_problems(path)]
    for principle in PRINCIPLES:
        count = sum(1 for name in explanations if name.split("/", 1)[0] == principle)
        if count < wanted:
            problems.append(f"{principle}: {count} explanations, not {wanted}")
    models: dict[str, tuple[str, str]] = {}
    for name in sorted(set(explanations) & set(ratings)):
        explainer = _model(explanations[name].with_suffix(".json"), problems)
        rater = _model(ratings[name], problems)
        models[name] = (explainer, rater)
    if problems:
        raise Missing("\n".join(problems))
    order: list[str] = []
    for principle in PRINCIPLES:
        names = sorted(name for name in ratings if name.split("/", 1)[0] == principle)
        random.Random(f"{SEED}-{principle}").shuffle(names)
        order += names[:review]
    marked = set(order)
    rows: list[list[Any]] = []
    csv_rows: list[dict[str, Any]] = []
    scores = {name: read_json(path) for name, path in ratings.items()}
    for name, rating in scores.items():
        principle, submission = name.split("/", 1)
        values = [rating[key] for key in RATING_KEYS]
        explainer, rater = models[name]
        same = "yes" if explainer == rater else "no"
        rows.append([f"`{principle}`", submission, *values, sum(values), explainer, rater, same,
                     "yes" if name in marked else "no"])
        csv_rows += [
            {"section": "VO5", "principle": principle, "item": submission, "measure": key, "value": rating[key]}
            for key in RATING_KEYS
        ] + [{"section": "VO5", "principle": principle, "item": submission, "measure": measure, "value": value}
             for measure, value in (("explainer model", explainer), ("rater model", rater),
                                    ("same model", same), ("owner review", int(name in marked)))]
    means = [f"{sum(r[key] for r in scores.values()) / len(scores):.2f}" for key in RATING_KEYS]
    total = f"{sum(sum(r[key] for key in RATING_KEYS) for r in scores.values()) / len(scores):.2f}"
    same_count = sum(1 for explainer, rater in models.values() if explainer == rater)
    rows.append(["mean", f"{len(scores)} explanations", *means, total, "all", "all", f"{same_count} same",
                 f"{len(marked)} marked"])
    lines = _table(["Principle", "Submission", *RATING_KEYS, "sum (0-6)", "explainer model", "rater model",
                    "same model", "owner review"], rows)
    lines += ["", f"For the owner's review ({review} per principle, seed 7):", ""]
    lines += [f"- `{name}`: `results/explanations/{name}.md`" for name in order]
    return lines, csv_rows


def _model(path: Path, problems: list[str]) -> str:
    """The ``model`` recorded in ``path`` by ``stage.py collect --model``."""
    try:
        data = read_json(path) if path.is_file() else None
    except (OSError, UnicodeDecodeError, ValueError):
        data = None
    model = data.get("model") if isinstance(data, dict) else None
    if not isinstance(model, str) or not model.strip():
        problems.append(f"{path}: no model recorded (stage.py collect --model)")
        return ""
    return model


def _judgments(base: Path, students: dict[str, list[str]]) -> dict[str, dict[str, dict[str, Any]]]:
    """run -> {"<p>/<student>": verdict}; every run covers every solution."""
    runs: dict[str, dict[str, dict[str, Any]]] = {}
    problems: list[str] = []
    for run_dir in sorted(path for path in (base / "results" / "judgments").glob("*") if path.is_dir()):
        found: dict[str, dict[str, Any]] = {}
        for principle, names in students.items():
            path = run_dir / f"{principle}.json"
            if not path.is_file():
                problems.append(f"{path} is missing")
                continue
            items = harness.pilot_score.judge_file(path, problems)
            found.update({f"{principle}/{item['id']}": item for item in items})
            problems += [f"{path}: no verdict on {name}" for name in names
                         if f"{principle}/{name}" not in found]
        runs[run_dir.name] = found
    if not runs:
        problems.append(f"{base / 'results' / 'judgments'}: no judge run; the realistic code needs at least one")
    if problems:
        raise Missing("\n".join(problems))
    return runs


def realistic(base: Path, wanted: int, tmp: Path) -> tuple[list[str], list[dict[str, Any]]]:
    students = {
        principle: sorted(path.name for path in harness.realistic(base, principle).glob("*") if path.is_dir())
        for principle in PRINCIPLES
    }
    total = sum(len(names) for names in students.values())
    problems = [f"{total} realistic solutions, not {wanted}"] if total < wanted else []
    metas: dict[str, dict[str, Any]] = {}
    for principle, names in students.items():
        for name in names:
            path = base / "data" / "meta" / principle / f"{name}.json"
            if not path.is_file():
                problems.append(f"{path} is missing")
            else:
                metas[f"{principle}/{name}"] = read_json(path)
    if problems:
        raise Missing("\n".join(problems))
    judges = _judgments(base, students)
    header = ["Principle", "Solution", "absolute imports", "`__init__.py`", "verdict", "errors", "not judged",
              *(f"judge {run}" for run in judges)]
    rows: list[list[Any]] = []
    csv_rows: list[dict[str, Any]] = []
    for principle, names in students.items():
        if not names:
            continue
        _, verdicts = harness.evaluate(
            harness.example_task(principle), harness.realistic(base, principle), tmp / "realistic" / principle
        )
        for name in names:
            row = verdicts.get(name)
            if row is None:
                raise Missing(f"{principle}: the report has no {name}")
            meta = metas[f"{principle}/{name}"]
            values: dict[str, Any] = {
                "absolute imports": "yes" if meta["absolute_imports"] else "no",
                "__init__.py": "yes" if (harness.realistic(base, principle) / name / "__init__.py").is_file() else "no",
                "verdict": row["verdict"],
                "errors": ", ".join(row["errors"]) or "none",
                "not judged": ", ".join(row.get("not_judged") or []) or "none",
            }
            for run, verdicts_of_run in judges.items():
                values[f"judge {run}"] = "violates" if verdicts_of_run[f"{principle}/{name}"]["violates"] else "does not violate"
            rows.append([f"`{principle}`", name, *values.values()])
            csv_rows += [
                {"section": "realistic", "principle": principle, "item": name, "measure": key, "value": value}
                for key, value in values.items()
            ]
    return _table(header, rows), csv_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=3, help="authors' runs per principle")
    parser.add_argument("--explanations", type=int, default=6, help="rated explanations per principle")
    parser.add_argument("--solutions", type=int, default=6, help="realistic solutions in all")
    parser.add_argument("--review", type=int, default=3, help="explanations per principle for the owner's review")
    parser.add_argument("--base", type=Path, default=HERE, help="the M6 directory")
    parser.add_argument("--pilot", type=Path, default=PILOT, help="the pilot directory")
    args = parser.parse_args(argv)
    base, pilot = args.base.resolve(), args.pilot.resolve()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            vo5_lines, vo5_rows = vo5(base, args.explanations, args.review)
            real_lines, real_rows = realistic(base, args.solutions, Path(tmp))
            vo3_lines, vo3_rows = vo3(base, pilot, args.runs, Path(tmp))
    except Missing as error:
        print(error, file=sys.stderr)
        return 1
    lines = [
        "# M6: the teaching workflow, evaluated (VO3, VO5, realistic code)",
        "",
        "Generated by `score.py`; do not edit by hand. Flagged = the verdict `failed` with a"
        " violation other than a missing required entity (unmatched, no verdict on the principle).",
        "",
        "## VO3: tasks written by agents",
        "",
        "`example` is the principle's own task; `run-N` an agent's `task.toml` with the same"
        " unannotated reference. Each runs on the pilot's injected errors, injected neutral defects"
        " and carriers; denominators after the slash.",
        "",
        *vo3_lines,
        "",
        "## VO5: explanations of the tool's findings",
        "",
        *vo5_lines,
        "",
        "## Realistic code: solutions without a skeleton",
        "",
        "The principle's own task on each solution (`class_overview`).",
        "",
        *real_lines,
        "",
    ]
    empty = [line for line in lines if line.startswith("| ") and _EMPTY.search(line[1:])]
    if empty:
        for line in empty:
            print(f"an empty cell: {line}", file=sys.stderr)
        return 1
    (base / f"{OUTPUT}.md").write_text("\n".join(lines), encoding="utf-8")
    with (base / f"{OUTPUT}.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["section", "principle", "item", "measure", "value"])
        writer.writeheader()
        writer.writerows([*vo3_rows, *vo5_rows, *real_rows])
    print(f"wrote {base / OUTPUT}.md and {base / OUTPUT}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
