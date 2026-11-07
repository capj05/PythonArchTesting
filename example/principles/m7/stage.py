"""Stage exactly the inputs one agent of M7 may see, collect its output, list the runs.

As in the pilot and M6 (whose helpers this reuses, ``harness.py``), no agent
works in the repository: each gets a fresh directory with nothing but its
inputs and writes its output there; ``collect`` validates it and copies it
into the M7 layout.

``stage.py <role> <principle> ...`` copies the inputs into
``<root>/m7-<role>-<principle>-<n>/`` (``--out DIR`` instead) and prints the
path; ``<root>`` is ``$PAT_STAGE_ROOT`` when set, else the pilot's stage root.
What the stage is for is kept beside it in ``<stage>.stage.json``:

============== ================================================ ================
role           inputs in the stage directory                     the agent writes
============== ================================================ ================
solver-novice  ``assignment.md`` (the pilot's; with ``--variant  ``<student>/``
               no-principle`` without the principle's section),
               ``submission.txt`` (as M6's, a package)
judge          ``assignment.md`` (the pilot's, whole),           ``verdicts.json``
               ``whole/<student>.md`` (one solution)
============== ================================================ ================

``solver-novice <p> --model M --variant V --run N``: the student is the fixed
name of (M, V, N) in ``harness.NAMES``. ``judge <p> <student> --run
<model>-<n>``: one judge run on one collected solution.

``stage.py collect <stage> [--force]`` copies the output to

- solver-novice: ``results/code/<p>/<student>/`` (Python files that parse)
  and ``results/meta/<p>/<student>.json`` (model, variant, run,
  ``__init__.py`` present);
- judge: ``results/judgments/<run>/<p>/<student>.json`` (one valid entry, the
  student's, as the pilot's ``score.py`` reads a judge file).

An existing destination is replaced only with ``--force``. Every collect,
refusals and ``--force`` replacements included, is appended to
``results/collect.log`` (time, stage, destination, outcome).

``stage.py plan [<p> ...]`` prints the dispatch list (Markdown) of the given
principles (default: every principle): the solver runs, then the judge runs,
each with the command that stages it and where ``collect`` puts its output.

Usage, from the repository root::

    python example/principles/m7/stage.py solver-novice encapsulation \\
        --model haiku --variant plain --run 1
    python example/principles/m7/stage.py collect <stage>
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402
from harness import ps, read_json, write_json  # noqa: E402

ROOT: Path = harness.m6_stage.ROOT
ROLES = ("solver-novice", "judge")
COMMAND = ".venv/bin/python example/principles/m7/stage.py"


def _destination(role: str, principle: str, out: Path | None) -> Path:
    if out is not None:
        out = out.resolve()
        if out.exists() and any(out.iterdir()):
            raise SystemExit(f"{out} is not empty; a stage starts fresh")
        return out
    prefix = f"m7-{role}-{principle}-"
    taken = [
        int(path.name[len(prefix) :])
        for path in ROOT.glob(prefix + "*")
        if path.is_dir() and path.name[len(prefix) :].isdigit()
    ]
    return ROOT / f"{prefix}{max(taken, default=0) + 1}"


def stage(args: argparse.Namespace) -> Path:
    """Write the inputs of ``args.role`` into a fresh directory; return it."""
    base: Path = args.base
    pilot: Path = args.pilot
    principle: str = args.principle
    source = harness.assignment(pilot, principle)
    text = source.read_text(encoding="utf-8")
    manifest: dict[str, Any] = {
        "role": args.role,
        "principle": principle,
        "base": str(base),
        "pilot": str(pilot),
    }
    texts: dict[str, str] = {}
    if args.role == "solver-novice":
        if args.model not in harness.MODELS:
            raise SystemExit(
                f"--model must be one of {harness.MODELS}, not {args.model!r}"
            )
        if args.variant not in harness.VARIANTS:
            raise SystemExit(
                f"--variant must be one of {harness.VARIANTS}, not {args.variant!r}"
            )
        if args.run not in [str(run) for run in harness.RUNS]:
            raise SystemExit(f"--run must be one of {harness.RUNS}, not {args.run!r}")
        student = harness.STUDENTS[(args.model, args.variant, int(args.run))]
        manifest.update(
            student=student, model=args.model, variant=args.variant, run=int(args.run)
        )
        if args.variant == "no-principle":
            text = harness.without_principle(text, str(source))
        texts["assignment.md"] = text
        texts["submission.txt"] = (
            harness.m6_stage.SUBMISSION.format(student=student)
            + harness.m6_stage.PACKAGE
        )
    elif args.role == "judge":
        run = args.run or ""
        if not ps._RUN.match(run):
            raise SystemExit(f"--run must be <model>-<run>, not {run!r}")
        student = args.student or ""
        harness.slot(student)
        code = harness.code_dir(base, principle) / student
        if not code.is_dir():
            raise SystemExit(f"{code} is missing; collect the solver first")
        manifest.update(run=run, student=student)
        texts["assignment.md"] = text
        texts[f"whole/{student}.md"] = harness.m6.pilot_prepare.whole(
            student, harness.files(code)
        )
    else:
        raise SystemExit(f"unknown role {args.role!r}")
    out = _destination(args.role, principle, args.out)
    for name, content in texts.items():
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_text(content, encoding="utf-8")
    ps._manifest_path(out).write_text(harness.dumps(manifest), encoding="utf-8")
    return out


LOG = "collect.log"


def log_path(base: Path) -> Path:
    """The append-only log of every ``collect`` under ``base``."""
    return base / "results" / LOG


def _log(base: Path, out: Path, target: Path | None, force: bool, outcome: str) -> None:
    """Append one line: time, stage, destination, ``--force``, outcome."""
    when = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    fields = [
        when,
        "collect --force" if force else "collect",
        str(out),
        str(target) if target is not None else "no destination",
        " ".join(outcome.split()),
    ]
    path = log_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log:
        log.write("\t".join(fields) + "\n")


def collect(out: Path, force: bool) -> Path:
    """Validate a stage's output and copy it into the M7 layout; return where.

    Every call whose stage has a manifest is appended to
    ``results/collect.log`` of its base, refusals (an output that does not
    parse, a wrong id, an existing destination without ``--force``)
    included, and a replacement under ``--force`` says so."""
    out = out.resolve()
    manifest = read_json(ps._need(ps._manifest_path(out)))
    base = Path(manifest["base"])
    target: Path | None = None
    try:
        target = _collect(out, manifest, force)
    except SystemExit as error:
        _log(base, out, target or _target(manifest), force, f"refused: {error}")
        raise
    return target


def _target(manifest: dict[str, Any]) -> Path | None:
    base, principle = Path(manifest["base"]), manifest["principle"]
    student = str(manifest.get("student"))
    if manifest["role"] == "solver-novice":
        return harness.code_dir(base, principle) / student
    if manifest["role"] == "judge":
        return harness.judgment_path(base, str(manifest["run"]), principle, student)
    return None


def _collect(out: Path, manifest: dict[str, Any], force: bool) -> Path:
    role, principle = manifest["role"], manifest["principle"]
    base, student = Path(manifest["base"]), str(manifest["student"])
    problems: list[str] = []
    if role == "solver-novice":
        source = ps._need(out / student)
        problems += harness.m6_stage._parses(source)
        target = harness.code_dir(base, principle) / student
    elif role == "judge":
        source = ps._need(out / "verdicts.json")
        items = harness.m6.pilot_score.judge_file(source, problems)
        ids = [str(item["id"]) for item in items]
        if not problems and ids != [student]:
            problems.append(f"{source}: the ids {ids} are not the staged [{student!r}]")
        target = harness.judgment_path(base, str(manifest["run"]), principle, student)
    else:
        raise SystemExit(f"{ps._manifest_path(out)}: unknown role {role!r}")
    if problems:
        raise SystemExit("\n".join(problems))
    existed = target.exists()
    ps._place(source, target, force)
    if role == "solver-novice":
        meta = {
            key: manifest[key]
            for key in ("student", "model", "variant", "run", "pilot")
        }
        meta["init"] = (target / "__init__.py").is_file()
        write_json(harness.meta_path(base, principle, student), meta)
    _log(base, out, target, force, "replaced" if existed else "placed")
    return Path(target)


def plan(names: list[str]) -> str:
    """The dispatch list of the principles ``names`` (Markdown)."""
    solvers = [
        "| # | Principle | Model | Variant | Run | Student | Stage it | `collect` puts it to |",
        "|---|---|---|---|---|---|---|---|",
    ]
    judges = [
        "| # | Principle | Judge run | Student | Stage it | `collect` puts it to |",
        "|---|---|---|---|---|---|",
    ]
    for principle in names:
        for model, variant, run in harness.SLOTS:
            student = harness.STUDENTS[(model, variant, run)]
            solvers.append(
                f"| S{len(solvers) - 1} | `{principle}` | {model} | {variant} | {run}"
                f" | {student} | `{COMMAND} solver-novice {principle} --model {model}"
                f" --variant {variant} --run {run}`"
                f" | `results/code/{principle}/{student}/` |"
            )
    for judge in harness.JUDGE_RUNS:
        for principle in names:
            for student in harness.NAMES:
                judges.append(
                    f"| J{len(judges) - 1} | `{principle}` | {judge} | {student}"
                    f" | `{COMMAND} judge {principle} {student} --run {judge}`"
                    f" | `results/judgments/{judge}/{principle}/{student}.json` |"
                )
    return "\n".join(
        [
            f"Solvers: {len(solvers) - 2} runs (prompt N, the model of the row).",
            "",
            *solvers,
            "",
            f"Judges: {len(judges) - 2} runs (prompt J; `sonnet-*` Sonnet, `haiku-*`"
            " Haiku), each after the row's solution is collected.",
            "",
            *judges,
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="role", required=True)
    for role in ROLES:
        sub = commands.add_parser(role)
        sub.add_argument("principle")
        if role == "judge":
            sub.add_argument("student")
            sub.add_argument("--run", help="<model>-<n>, e.g. sonnet-1")
        else:
            sub.add_argument("--model", help=f"one of {harness.MODELS}")
            sub.add_argument("--variant", help=f"one of {harness.VARIANTS}")
            sub.add_argument("--run", help=f"one of {harness.RUNS}")
        sub.add_argument("--base", type=Path, default=HERE, help="the M7 directory")
        sub.add_argument(
            "--pilot", type=Path, default=harness.PILOT, help="the pilot directory"
        )
        sub.add_argument(
            "--out", type=Path, help=f"the stage directory (default under {ROOT})"
        )
    back = commands.add_parser("collect")
    back.add_argument("stage", type=Path)
    back.add_argument(
        "--force", action="store_true", help="replace an existing destination"
    )
    listing = commands.add_parser("plan")
    listing.add_argument("principles", nargs="*")
    args = parser.parse_args(argv)
    if args.role == "collect":
        print(collect(args.stage, args.force))
        return 0
    known = harness.principles()
    if args.role == "plan":
        chosen = args.principles or list(known)
        unknown = [name for name in chosen if name not in known]
        if unknown:
            raise SystemExit(f"the principles must be among {known}, not {unknown}")
        print(plan(chosen))
        return 0
    args.base, args.pilot = args.base.resolve(), args.pilot.resolve()
    if args.principle not in known:
        raise SystemExit(
            f"the principle must be one of {known}, not {args.principle!r}"
        )
    print(stage(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
