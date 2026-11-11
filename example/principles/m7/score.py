"""Score M7: natural violations, the tool and the judges on them, the owner's VO5.

Writes ``results.md`` into the M7 directory (``--base``, by default the one of
this file). The tool's verdicts are not read from anywhere: they are computed
now, with the current tool, over the stored solutions
(``results/code/<p>/<student>/``), so the data stays valid when the tool
improves. Read:

- ``results/meta/<p>/<student>.json``: model, variant, run of each solution;
- ``results/judgments/<run>/<p>/<student>.json`` for every run of
  ``--judges`` (``sonnet-1,sonnet-2,haiku-1``);
- ``review.md`` (``forms.py review``, filled in by the owner): the ground
  truth, ``violates: yes|no`` per sampled solution;
- ``owner_vo5.md`` (``forms.py vo5``, filled in by the owner) beside the M6
  rater's scores (``<m6>/results/ratings/<p>/<s>.json``) of the explanations
  listed in ``<m6>/results-vo3-vo5.md``.

Tables, per principle and variant (``plain``, ``no-principle``, and both):

1. all solutions: how many, how many the owner reviewed, how many the tool
   and each judge run flag, the tool's solutions without a verdict, and on
   how many the two runs of ``--stability`` (``sonnet-1,sonnet-2``) differ;
2. against the owner's ground truth: the natural violations among the
   reviewed solutions, and per decider how many of them it detects and how
   many of the reviewed clean ones it flags (FP);
3. VO5: per explanation the owner's and the rater's scores (location,
   principle, reason) and how many of the three are equal;
4. every solution with every verdict.

A solution not in ``review.md`` that would enter its sample now (flagged by
the tool or a judge, or the tool now disagrees with a judge: the tool
changed since the form was generated) is listed under "Needs review: not in
the form" and not counted against the ground truth.

Flagged by the tool = the verdict ``failed`` with a violation other than a
missing required entity (as in M6). Where the owner has not answered, a cell
reads ``pending owner review``: that is not an error (exit 0).

Exits 1, writing nothing, when an input is missing or malformed: a principle
with solutions but fewer than ``--solutions``, a solution without its meta
file, a judge run without a verdict on a solution, a value in a form out of
range or a form that does not parse (``forms.py``: the item set of its
header, one heading per item, one line per field, no stray line), a form
naming a solution or explanation that does not exist, a meta file whose
(model, variant, run) is not the student's fixed slot, an M6 rating
missing; or when a cell would be empty or ``–``.

Usage, from the repository root::

    python example/principles/m7/score.py [--solutions 12] [--base DIR] [--m6 DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402
import forms  # noqa: E402

OUTPUT = "results.md"
PENDING = "pending owner review"
ALL = "both"
_table = harness.m6_score._table
_EMPTY = harness.m6_score._EMPTY


class Missing(Exception):
    """A required input is missing or malformed."""


def _verdict(violates: bool) -> str:
    return "violates" if violates else "does not violate"


def _rate(hits: int, total: int) -> str:
    return f"{hits}/{total}"


def _meta_problems(path: Path, student: str, meta: dict[str, Any]) -> list[str]:
    """The meta file must name the student's fixed slot (``harness.slot``)."""
    try:
        expected = harness.slot(student)
    except SystemExit as error:
        return [f"{path}: {error}"]
    found = (meta.get("model"), meta.get("variant"), meta.get("run"))
    if found != expected or meta.get("student") != student:
        return [
            f"{path}: (model, variant, run) is {found} for {meta.get('student')!r},"
            f" but {student} is the fixed student of {expected}"
        ]
    return []


def load(base: Path, wanted: int, judges: tuple[str, ...]) -> list[dict[str, Any]]:
    """One record per solution: principle, student, meta, the tool now, the
    judges."""
    problems: list[str] = []
    records: list[dict[str, Any]] = []
    for principle in harness.principles():
        names = harness.students(base, principle)
        if not names:
            continue
        if len(names) < wanted:
            problems.append(f"{principle}: {len(names)} solutions, not {wanted}")
        judged = harness.judgments(base, principle, judges, problems)
        metas = {}
        for name in names:
            path = harness.meta_path(base, principle, name)
            if not path.is_file():
                problems.append(f"{path} is missing")
            else:
                metas[name] = harness.read_json(path)
                problems += _meta_problems(path, name, metas[name])
        if problems:
            continue
        tool = harness.tool_verdicts(base, principle)
        for name in names:
            records.append(
                {
                    "principle": principle,
                    "student": name,
                    "meta": metas[name],
                    "tool": tool[name],
                    "judges": {run: judged[run][name] for run in judges},
                }
            )
    if not records and not problems:
        problems.append(f"{base / 'results' / 'code'}: no solution collected")
    if problems:
        raise Missing("\n".join(problems))
    return records


def _flags(record: dict[str, Any], decider: str) -> bool:
    if decider == "tool":
        return bool(record["tool"]["verdict"] == harness.TOOL_VIOLATES)
    return bool(record["judges"][decider])


def _groups(
    records: list[dict[str, Any]],
) -> list[tuple[str, str, list[dict[str, Any]]]]:
    groups = []
    for principle in sorted({record["principle"] for record in records}):
        mine = [record for record in records if record["principle"] == principle]
        for variant in harness.VARIANTS:
            groups.append(
                (
                    principle,
                    variant,
                    [r for r in mine if r["meta"]["variant"] == variant],
                )
            )
        groups.append((principle, ALL, mine))
    return groups


def overview(
    records: list[dict[str, Any]],
    truth: dict[str, Any],
    judges: tuple[str, ...],
    stability: tuple[str, ...],
) -> list[str]:
    header = [
        "Principle",
        "Variant",
        "solutions",
        "owner reviewed",
        "tool flags",
        *(f"judge {run} flags" for run in judges),
        "tool without a verdict",
        f"{' vs '.join(stability)} differ",
    ]
    rows = []
    for principle, variant, group in _groups(records):
        keys = [f"{r['principle']}/{r['student']}" for r in group]
        answered = sum(
            1 for key in keys if key in truth and truth[key]["violates"] is not None
        )
        waiting = sum(
            1 for key in keys if key in truth and truth[key]["violates"] is None
        )
        reviewed = _rate(answered, len(group)) + (
            f", {waiting} {PENDING}" if waiting else ""
        )
        no_verdict = sum(
            1
            for r in group
            if r["tool"]["verdict"] not in (harness.TOOL_VIOLATES, harness.TOOL_PASSES)
        )
        differ = sum(
            1 for r in group if r["judges"][stability[0]] != r["judges"][stability[1]]
        )
        rows.append(
            [
                f"`{principle}`",
                variant,
                len(group),
                reviewed,
                _rate(sum(_flags(r, "tool") for r in group), len(group)),
                *(
                    _rate(sum(_flags(r, run) for r in group), len(group))
                    for run in judges
                ),
                _rate(no_verdict, len(group)),
                _rate(differ, len(group)),
            ]
        )
    return list(_table(header, rows))


def _key(record: dict[str, Any]) -> str:
    return f"{record['principle']}/{record['student']}"


def against_truth(
    records: list[dict[str, Any]],
    truth: dict[str, Any],
    judges: tuple[str, ...],
    stale: set[str],
) -> list[str]:
    deciders = ("tool", *judges)
    header = [
        "Principle",
        "Variant",
        "natural violations (owner)",
        *("tool" if d == "tool" else f"judge {d}" for d in deciders),
    ]
    finished = bool(truth) and all(
        answer["violates"] is not None for answer in truth.values()
    )
    rows = []
    for principle, variant, group in _groups(records):
        known = [
            (r, truth[_key(r)]["violates"])
            for r in group
            if truth.get(_key(r), {}).get("violates") is not None
        ]
        outside = sum(1 for r in group if _key(r) in stale)
        missed = f"; {outside} needs review, not in the form" if outside else ""
        if not known:
            sampled = any(_key(r) in truth for r in group)
            cell = "none in the sample" if finished and not sampled else PENDING
            rows.append(
                [f"`{principle}`", variant, cell + missed, *[cell] * len(deciders)]
            )
            continue
        bad = [r for r, violates in known if violates]
        clean = [r for r, violates in known if not violates]
        cells = []
        for decider in deciders:
            found = (
                f"detects {_rate(sum(_flags(r, decider) for r in bad), len(bad))}"
                if bad
                else "detects n/a (no violation)"
            )
            false = (
                f"FP {_rate(sum(_flags(r, decider) for r in clean), len(clean))}"
                if clean
                else "FP n/a (no clean one)"
            )
            silent = (
                sum(1 for r, _ in known if not _decided(r)) if decider == "tool" else 0
            )
            cells.append(
                f"{found}; {false}" + (f"; {silent} no verdict" if silent else "")
            )
        rows.append(
            [
                f"`{principle}`",
                variant,
                f"{_rate(len(bad), len(known))} reviewed{missed}",
                *cells,
            ]
        )
    return list(_table(header, rows))


def _decided(record: dict[str, Any]) -> bool:
    return record["tool"]["verdict"] in (harness.TOOL_VIOLATES, harness.TOOL_PASSES)


def needs_review(
    records: list[dict[str, Any]], truth: dict[str, Any], form: bool
) -> list[dict[str, Any]]:
    """The solutions not in ``review.md`` that would enter its sample now:
    flagged by the tool or a judge, or the tool now disagrees with a judge
    (``forms.must_review``). Only when the form exists."""
    if not form:
        return []
    return [
        r
        for r in records
        if _key(r) not in truth and forms.must_review(r["tool"]["verdict"], r["judges"])
    ]


def vo5(m6_base: Path, owner: dict[str, Any], wanted: int) -> list[str]:
    items = forms.vo5_items(m6_base, wanted)
    problems = [
        f"{forms.VO5}: `{name}` is not one of the explanations of {forms.M6_RESULTS}"
        for name in owner
        if name not in items
    ]
    keys = harness.m6.RATING_KEYS
    header = [
        "Principle",
        "Explanation",
        "owner (location, principle, reason)",
        "rater (location, principle, reason)",
        "rater model",
        "equal parts",
        "owner's note",
    ]
    rows: list[list[Any]] = []
    rated = equal = whole = 0
    models = set()
    for name in items:
        principle, submission = name.split("/", 1)
        path = m6_base / "results" / "ratings" / principle / f"{submission}.json"
        found = (
            harness.m6.rating_problems(path)
            if path.is_file()
            else [f"{path} is missing"]
        )
        if found:
            problems += found
            continue
        rating = harness.read_json(path)
        model = str(rating.get("model") or "not recorded")
        models.add(model)
        theirs = [rating[key] for key in keys]
        mine = owner.get(name, {})
        if any(mine.get(key) is None for key in keys):
            rows.append(
                [
                    f"`{principle}`",
                    submission,
                    PENDING,
                    ", ".join(map(str, theirs)),
                    model,
                    PENDING,
                    mine.get("note") or "none",
                ]
            )
            continue
        ours = [mine[key] for key in keys]
        same = sum(1 for a, b in zip(ours, theirs) if a == b)
        rated, equal, whole = rated + 1, equal + same, whole + (same == len(keys))
        rows.append(
            [
                f"`{principle}`",
                submission,
                ", ".join(map(str, ours)),
                ", ".join(map(str, theirs)),
                model,
                _rate(same, len(keys)),
                mine.get("note") or "none",
            ]
        )
    if problems:
        raise Missing("\n".join(problems))
    summary = (
        f"{_rate(equal, len(keys) * rated)} parts, {_rate(whole, rated)} explanations all equal"
        if rated
        else PENDING
    )
    rows.append(
        [
            "all",
            f"{len(items)} explanations",
            f"{_rate(rated, len(items))} rated",
            "as listed",
            ", ".join(sorted(models)) or "none",
            summary,
            "n/a",
        ]
    )
    return list(_table(header, rows))


def solutions(
    records: list[dict[str, Any]],
    truth: dict[str, Any],
    judges: tuple[str, ...],
    stale: set[str],
) -> list[str]:
    header = [
        "Principle",
        "Solution",
        "model",
        "variant",
        "run",
        "`__init__.py`",
        "tool",
        "tool errors",
        *(f"judge {run}" for run in judges),
        "owner",
    ]
    rows = []
    for r in records:
        answer = truth.get(f"{r['principle']}/{r['student']}")
        owner = (
            (
                "not in the form, needs review"
                if _key(r) in stale
                else "not in the sample"
            )
            if answer is None
            else PENDING if answer["violates"] is None else _verdict(answer["violates"])
        )
        meta = r["meta"]
        rows.append(
            [
                f"`{r['principle']}`",
                r["student"],
                meta["model"],
                meta["variant"],
                meta["run"],
                "yes" if meta["init"] else "no",
                r["tool"]["verdict"],
                ", ".join(r["tool"]["errors"]) or "none",
                *(_verdict(r["judges"][run]) for run in judges),
                owner,
            ]
        )
    return list(_table(header, rows))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--solutions",
        type=int,
        default=len(harness.SLOTS),
        help="solutions per principle (that has any)",
    )
    parser.add_argument("--judges", default=",".join(harness.JUDGE_RUNS))
    parser.add_argument(
        "--stability",
        default=",".join(harness.STABILITY),
        help="the two judge runs compared for stability",
    )
    parser.add_argument("--vo5-items", type=int, default=6)
    parser.add_argument("--base", type=Path, default=HERE, help="the M7 directory")
    parser.add_argument("--m6", type=Path, default=harness.M6, help="the M6 directory")
    args = parser.parse_args(argv)
    base, m6_base = args.base.resolve(), args.m6.resolve()
    judges = tuple(run for run in args.judges.split(",") if run)
    stability = tuple(run for run in args.stability.split(",") if run)
    if len(stability) != 2 or not set(stability) <= set(judges):
        print(
            f"--stability must be two of --judges {judges}, not {stability}",
            file=sys.stderr,
        )
        return 1
    problems: list[str] = []
    truth = forms.read_review(base / forms.REVIEW, problems)
    owner = forms.read_vo5(base / forms.VO5, problems)
    try:
        if problems:
            raise Missing("\n".join(problems))
        records = load(base, args.solutions, judges)
        unknown = sorted(
            set(truth) - {f"{r['principle']}/{r['student']}" for r in records}
        )
        if unknown:
            raise Missing(
                f"{forms.REVIEW} names solutions that are not collected: {unknown}"
            )
        vo5_lines = vo5(m6_base, owner, args.vo5_items)
    except (Missing, SystemExit) as error:
        print(error, file=sys.stderr)
        return 1
    changed = [
        f"- `{name}`: `{answer['tool']}` in {forms.REVIEW}, `{r['tool']['verdict']}` now"
        for r in records
        if (name := f"{r['principle']}/{r['student']}") in truth
        and (answer := truth[name])["tool"] != r["tool"]["verdict"]
    ]
    outside = needs_review(records, truth, (base / forms.REVIEW).is_file())
    stale = {_key(r) for r in outside}
    answered = sum(1 for answer in truth.values() if answer["violates"] is not None)
    lines = [
        "# M7: natural violations, the tool and the judges, the owner's VO5",
        "",
        "Generated by `score.py`; do not edit by hand. The tool's verdicts are computed by"
        " the tool as it is now over the stored solutions; flagged by the tool = the verdict"
        " `failed` with a violation other than a missing required entity. A judge flags a"
        f" solution it says violates the principle. `{PENDING}`: the owner has not answered"
        f" yet. The owner answered {answered} of the {len(truth)} solutions of `{forms.REVIEW}`"
        f" (out of {len(records)}).",
        "",
        "Read these numbers with the threats to their validity in mind (sample-based ground"
        " truth enriched with flagged and disputed solutions, small n, one model family,"
        " LLM-written novice code, the owner as the tool's author): `README.md`, section"
        ' "Validity threats".',
        "",
        "## All solutions, per principle and variant",
        "",
        *overview(records, truth, judges, stability),
        "",
        "## Against the owner's ground truth",
        "",
        "Over the solutions the owner reviewed: natural violations = those the owner says"
        " violate the principle; per decider, how many of them it flags (detects), and how"
        " many of the reviewed clean ones it flags (FP); `n no verdict`: on n of the"
        " reviewed ones the tool gave no verdict. The sample is enriched with every"
        " solution a decider flags or the deciders dispute, so these are counts on the"
        " sample, not rates on all solutions. `none in the sample`: the owner answered"
        " every solution of the form and none is of this row. A solution that would enter"
        " the sample now but is not in the form is not counted here; it is listed under"
        ' "Needs review: not in the form".',
        "",
        *against_truth(records, truth, judges, stale),
        "",
        "## VO5: the owner and the M6 rater on the same explanations",
        "",
        *vo5_lines,
        "",
        "## Every solution",
        "",
        *solutions(records, truth, judges, stale),
        "",
    ]
    if outside:
        lines += [
            "## Needs review: not in the form",
            "",
            f"Not in `{forms.REVIEW}`, but flagged now by the tool or a judge, or the tool"
            " now disagrees with a judge, so they would enter the sample; they are not"
            " counted against the ground truth. Regenerate the form (`forms.py review"
            " --force`, then copy the answers over) or review them by hand:",
            "",
            *(
                f"- `{_key(r)}`: tool `{r['tool']['verdict']}`; "
                + "; ".join(f"{run} {_verdict(r['judges'][run])}" for run in judges)
                for r in outside
            ),
            "",
        ]
    if changed:
        lines += [
            f"The tool's verdict changed since `{forms.REVIEW}` was generated:",
            "",
            *changed,
            "",
        ]
    empty = [
        line for line in lines if line.startswith("| ") and _EMPTY.search(line[1:])
    ]
    if empty:
        for line in empty:
            print(f"an empty cell: {line}", file=sys.stderr)
        return 1
    (base / OUTPUT).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {base / OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
