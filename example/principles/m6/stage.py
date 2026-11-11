"""Stage exactly the inputs one agent of the M6 evaluation may see, and collect its output.

As in the pilot (``../pilot/stage.py``, whose helpers this reuses), no agent
works in the repository: each gets a fresh directory with nothing but its
inputs and writes its output there; ``collect`` validates it and copies it
into the M6 layout (``harness.py``).

``stage.py <role> <principle> ...`` copies the inputs into
``<root>/m6-<role>-<principle>-<n>/`` (``--out DIR`` instead) and prints the
path; ``<root>`` is ``$PAT_STAGE_ROOT`` when set, else the pilot's stage root.
What the stage is for is kept beside it in ``<stage>.stage.json``, and the
tool's report the explainer's findings come from in ``<stage>.report/``, both
outside the agent's directory:

=========== ===================================================== =====================
role        inputs in the stage directory                          the agent writes
=========== ===================================================== =====================
author      ``principle.json`` (``describe_principle``),           ``task/task.toml``
(``--run``) ``task/reference/`` (unannotated), ``tools.txt``
            (the commands it may run, ``tools.py describe|
            describe_marker|prepare``, under the MCP
            descriptions of their tools)
explainer   ``principle.json`` (``name``, ``summary``, ``why``),   ``explanation.md``
            ``findings.json`` (``explain_target`` with the
            principle), ``code/`` (the submission)
rater       ``principle.json``, ``code/``, ``explanation.md``      ``rating.json``
            (the explainer's), ``rubric.md``
solver      ``assignment.md`` (the pilot's), ``submission.txt``    ``<ident_surname>/``
(``--student``, ``--absolute-imports``)
judge       ``assignment.md``, ``whole/<ident_surname>.md`` for    ``verdicts.json``
(``--run``) every realistic solution of the principle
=========== ===================================================== =====================

A submission of ``explainer`` and ``rater`` is a pilot injected error
(``<id>-<carrier_>``, under ``<pilot>/<p>/injected/err/``) or a realistic
solution (``<ident_surname>``). The explainer's findings come from
``--report`` (a report.json that has the submission as a target) or, by
default, from a fresh run of the principle's own task on the submission alone;
a submission the tool does not fail is refused.

``stage.py candidates <principle> [--count 6]`` prints the pilot injected
errors the principle's own task fails, in a seeded order: the first ``count``
are the explainers' submissions.

``stage.py collect <stage> [--force] [--model M]`` copies the output to

- author: ``results/tasks/<p>/run-<N>/task.toml`` (valid TOML, the stage's
  principle, the reference unchanged);
- explainer (``--model`` required): ``results/explanations/<p>/<submission>.md``
  (not empty) and ``<submission>.json`` beside it (``{"model": M}``), and the
  findings to ``data/findings/<p>/<submission>.json``;
- rater (``--model`` required): ``results/ratings/<p>/<submission>.json``
  (``location``, ``principle``, ``reason`` each 0-2, ``comment`` a string,
  and ``model`` M added);
- solver: ``data/solutions/<p>/<ident_surname>/`` (Python files that parse;
  with ``--absolute-imports`` at least one module importing a sibling by its
  plain name) and ``data/meta/<p>/<ident_surname>.json``;
- judge: ``results/judgments/<run>/<p>.json`` (one valid entry per staged
  solution, as the pilot's ``score.py`` reads a judge file).

An existing destination is replaced only with ``--force``.

Usage, from the repository root::

    python example/principles/m6/stage.py author encapsulation --run 1
    python example/principles/m6/stage.py collect <stage>
"""

from __future__ import annotations

import argparse
import ast
import inspect
import json
import os
import random
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402
from harness import PILOT, STUDENT, copy_code, files, read_json, write_json  # noqa: E402

ps = harness.pilot_stage
ROOT: Path = Path(os.environ["PAT_STAGE_ROOT"]) if os.environ.get("PAT_STAGE_ROOT") else ps.ROOT
ROLES = ("author", "explainer", "rater", "solver", "judge")
SEED = 7
TOOLS = HERE / "tools.py"

RUBRIC = """\
# Rubric: rate one explanation of a student's mistake

Read the student's code in `code/`, the explanation in `explanation.md`, and
the principle the code was checked for in `principle.json` (its `name`,
`summary` and `why`). Rate three things, each 0, 1 or 2, by what the code
really does:

- **location**: does the explanation point at the right place?
  2 = the right file and function, and the line or statement that breaks the
  principle; 1 = the right function or file, but the place is vague or partly
  wrong; 0 = a wrong place, or none.
- **principle**: does it name the principle of `principle.json`, and say what
  that principle asks (its `summary`)? 2 = named and stated correctly; 1 =
  named, but stated vaguely or partly wrongly; 0 = a wrong principle, or none.
- **reason**: does it say correctly why this code is a problem and how to fix
  it? 2 = the reason is true of this code and the fix would remove the problem;
  1 = a generic or partly wrong reason, or no usable fix; 0 = a wrong reason.

A claim about the code that is false (a line that does not do what the
explanation says) lowers the score of the part it belongs to.
"""

SUBMISSION = """\
Submit your solution as the directory `{student}/` (your package; it is named
after you: your login and surname).
"""
PACKAGE = "Make it a Python package: it contains `__init__.py`.\n"
ABSOLUTE = (
    "Import sibling modules by their plain name (`import inventory` /\n"
    "`from inventory import Inventory`), as you do when you run the code from\n"
    "inside its folder; this overrides the import style shown in the assignment.\n"
    "The directory need not contain `__init__.py`.\n"
)


def _destination(role: str, principle: str, out: Path | None) -> Path:
    if out is not None:
        out = out.resolve()
        if out.exists() and any(out.iterdir()):
            raise SystemExit(f"{out} is not empty; a stage starts fresh")
        return out
    prefix = f"m6-{role}-{principle}-"
    taken = [
        int(path.name[len(prefix):])
        for path in ROOT.glob(prefix + "*")
        if path.is_dir() and path.name[len(prefix):].isdigit()
    ]
    return ROOT / f"{prefix}{max(taken, default=0) + 1}"


def _run_label(run: str | None) -> str:
    if not run or not ps._RUN.match(run):
        raise SystemExit(f"--run must be <model>-<run>, not {run!r}")
    return run


def _comment(text: str) -> list[str]:
    return [f"# {line}".rstrip() for line in inspect.cleandoc(text).splitlines()]


def _tools_txt(principle: str, task: Path) -> str:
    """The author's commands, each under the description an MCP client sees
    for its tool; the server's instructions first."""
    from pythonarchtesting.mcp_server import server

    lines = [
        "# The three tools you may use, each run by the command line under its",
        "# description (it prints JSON). The descriptions are those an MCP client",
        "# sees; the server's instructions come first and name tools you do not have.",
        "#",
        *_comment(server.INSTRUCTIONS),
        "#",
        "# describe_principle(principle_id):",
        *_comment(server.describe_principle.__doc__ or ""),
        f"{sys.executable} {TOOLS} describe {principle}",
        "#",
        "# describe_marker(name):",
        *_comment(server.describe_marker.__doc__ or ""),
        f"{sys.executable} {TOOLS} describe_marker <name>",
        "#",
        "# prepare_task(task_dir):",
        *_comment(server.prepare_task.__doc__ or ""),
        f"{sys.executable} {TOOLS} prepare {task}",
    ]
    return "\n".join(lines) + "\n"


def _principle_json(principle: str) -> str:
    """The principle's ``name``, ``summary`` and ``why`` (``describe_principle``)."""
    from pythonarchtesting.mcp_server import principles

    entry = principles.describe_principle(principle)
    chosen = {key: entry[key] for key in ("name", "summary", "why")}
    return json.dumps(chosen, indent=1, ensure_ascii=False) + "\n"


def _findings(args: argparse.Namespace, code: Path, reports: Path) -> dict[str, Any]:
    """``explain_target`` with the principle for the submission: from
    ``--report``, or from a fresh run of the principle's task on it alone,
    whose report goes to ``reports`` (outside the agent's directory)."""
    if args.report is not None:
        return harness.explain(str(args.report.resolve()), args.submission, args.principle)
    name = args.submission if STUDENT.match(args.submission) else "submission"
    with tempfile.TemporaryDirectory() as tmp:
        targets = Path(tmp) / "targets"
        copy_code(code, targets / name)
        report, _ = harness.evaluate(harness.example_task(args.principle), targets, reports)
    return harness.explain(report, name, args.principle)


def stage(args: argparse.Namespace) -> Path:
    """Write the inputs of ``args.role`` into a fresh directory; return it."""
    base: Path = args.base
    pilot: Path = args.pilot
    principle: str = args.principle
    task = harness.example_task(principle)
    manifest: dict[str, Any] = {
        "role": args.role, "principle": principle, "base": str(base), "pilot": str(pilot),
    }
    copies: dict[str, Path] = {}
    texts: dict[str, str] = {}
    out = _destination(args.role, principle, args.out)
    if args.role == "author":
        if not isinstance(args.run, str) or not args.run.isdigit() or int(args.run) < 1:
            raise SystemExit(f"--run must be a run number (1, 2, ...), not {args.run!r}")
        manifest["run"] = int(args.run)
        copies["task/reference"] = task / "reference"
        from pythonarchtesting.mcp_server import principles

        texts["principle.json"] = json.dumps(
            principles.describe_principle(principle), indent=1, ensure_ascii=False
        ) + "\n"
    elif args.role in ("explainer", "rater"):
        if not args.submission:
            raise SystemExit(f"{args.role} needs the submission")
        code = harness.submission(base, pilot, principle, args.submission)
        manifest["submission"] = args.submission
        copies["code"] = code
        texts["principle.json"] = _principle_json(principle)
        if args.role == "explainer":
            found = _findings(args, code, out.with_name(out.name + ".report"))
            if found["verdict"] != "failed":
                raise SystemExit(
                    f"the tool does not fail {args.submission} ({found['verdict']}): nothing to explain"
                )
            texts["findings.json"] = json.dumps(found, indent=1, ensure_ascii=False) + "\n"
        else:
            explanation = base / "results" / "explanations" / principle / f"{args.submission}.md"
            copies["explanation.md"] = ps._need(explanation)
            texts["rubric.md"] = RUBRIC
    elif args.role == "solver":
        student = args.student or ""
        if not STUDENT.match(student):
            raise SystemExit(f"--student must look like capj05_capsky, not {student!r}")
        manifest.update(student=student, absolute_imports=bool(args.absolute_imports))
        copies["assignment.md"] = ps._need(pilot / principle / "assignment.md")
        texts["submission.txt"] = SUBMISSION.format(student=student) + (
            ABSOLUTE if args.absolute_imports else PACKAGE
        )
    elif args.role == "judge":
        manifest["run"] = _run_label(args.run)
        solutions = harness.realistic(base, principle)
        students = sorted(path.name for path in solutions.glob("*") if path.is_dir())
        if not students:
            raise SystemExit(f"no realistic solution under {solutions}; collect the solvers first")
        manifest["ids"] = students
        copies["assignment.md"] = ps._need(pilot / principle / "assignment.md")
        for student in students:
            code = files(solutions / student)
            texts[f"whole/{student}.md"] = harness.pilot_prepare.whole(student, code)
    else:
        raise SystemExit(f"unknown role {args.role!r}")
    out.mkdir(parents=True, exist_ok=True)
    if args.role == "author":
        texts["tools.txt"] = _tools_txt(principle, out / "task")
    for name, source in copies.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            copy_code(source, target)
        else:
            target.write_bytes(source.read_bytes())
    for name, text in texts.items():
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_text(text, encoding="utf-8")
    ps._manifest_path(out).write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return out


def _parses(root: Path) -> list[str]:
    code = files(root)
    if not code:
        return [f"{root} has no Python file"]
    problems = []
    for name, text in code.items():
        try:
            ast.parse(text, filename=name)
        except SyntaxError as error:
            problems.append(f"{root / name}: does not parse ({error.msg}, line {error.lineno})")
    return problems


def _sibling_imports(root: Path) -> list[str]:
    """The modules of ``root`` imported by their plain name from a sibling."""
    modules = {Path(name).stem for name in files(root) if "/" not in name} - {"__init__"}
    found = []
    for name, text in files(root).items():
        for node in ast.walk(ast.parse(text, filename=name)):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in modules:
                found.append(node.module)
            elif isinstance(node, ast.Import):
                found += [alias.name for alias in node.names if alias.name in modules]
    return found


def collect(out: Path, force: bool, model: str | None = None) -> Path:
    """Validate a stage's output and copy it into the M6 layout; return where.
    ``model`` (the agent's model) is required for an explainer and a rater."""
    out = out.resolve()
    manifest = read_json(ps._need(ps._manifest_path(out)))
    role, principle = manifest["role"], manifest["principle"]
    base, pilot = Path(manifest["base"]), Path(manifest["pilot"])
    problems: list[str] = []
    if role in ("explainer", "rater") and not model:
        raise SystemExit(f"collect of a {role} needs --model (the agent's model)")
    if role == "author":
        source = ps._need(out / "task" / "task.toml")
        try:
            declared = tomllib.loads(source.read_text(encoding="utf-8")).get("principle")
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            raise SystemExit(f"{source}: not valid TOML ({error})") from error
        if declared != principle:
            problems.append(f"{source}: principle is {declared!r}, not {principle!r}")
        if files(out / "task" / "reference") != files(harness.example_task(principle) / "reference"):
            problems.append(f"{out / 'task' / 'reference'} was changed; the task must keep the reference")
        target = base / "results" / "tasks" / principle / f"run-{manifest['run']}" / "task.toml"
    elif role == "explainer":
        source = ps._need(out / "explanation.md")
        if not source.read_text(encoding="utf-8").strip():
            problems.append(f"{source} is empty")
        target = base / "results" / "explanations" / principle / f"{manifest['submission']}.md"
    elif role == "rater":
        source = ps._need(out / "rating.json")
        problems += harness.rating_problems(source)
        target = base / "results" / "ratings" / principle / f"{manifest['submission']}.json"
    elif role == "solver":
        student = manifest["student"]
        source = ps._need(out / student)
        problems += _parses(source)
        if not problems and manifest["absolute_imports"] and not _sibling_imports(source):
            problems.append(f"{source}: no module imports a sibling by its plain name")
        target = harness.realistic(base, principle) / str(student)
    elif role == "judge":
        source = ps._need(out / "verdicts.json")
        items = harness.pilot_score.judge_file(source, problems)
        ids = sorted(str(item["id"]) for item in items)
        if not problems and ids != sorted(manifest["ids"]):
            problems.append(f"{source}: the ids {ids} are not the staged {sorted(manifest['ids'])}")
        target = base / "results" / "judgments" / str(manifest["run"]) / f"{principle}.json"
    else:
        raise SystemExit(f"{ps._manifest_path(out)}: unknown role {role!r}")
    if problems:
        raise SystemExit("\n".join(problems))
    ps._place(source, target, force)
    if role == "explainer":
        ps._place(out / "findings.json", base / "data" / "findings" / principle / target.with_suffix(".json").name, True)
        write_json(target.with_suffix(".json"), {"model": model})
    if role == "rater":
        write_json(target, {**read_json(target), "model": model})
    if role == "solver":
        meta = {
            "student": manifest["student"],
            "absolute_imports": manifest["absolute_imports"],
            "init": (target / "__init__.py").is_file(),
            "pilot": str(pilot),
        }
        write_json(base / "data" / "meta" / principle / f"{manifest['student']}.json", meta)
    return Path(target)


def candidates(args: argparse.Namespace) -> list[str]:
    """The pilot injected errors the principle's task fails, seeded order."""
    pool = {
        name: item
        for name, item in harness.pilot_pool(args.pilot, args.principle).items()
        if item["kind"] == "err"
    }
    with tempfile.TemporaryDirectory() as tmp:
        targets = Path(tmp) / "targets"
        for name, item in pool.items():
            copy_code(args.pilot / args.principle / item["path"], targets / name)
        _, rows = harness.evaluate(harness.example_task(args.principle), targets, Path(tmp) / "reports")
    found = sorted(
        Path(item["path"]).parent.name
        for name, item in pool.items()
        if harness.failed_by_violation(rows[name])
    )
    random.Random(f"{SEED}-{args.principle}").shuffle(found)
    return found[: args.count]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="role", required=True)
    for role in (*ROLES, "candidates"):
        sub = commands.add_parser(role)
        sub.add_argument("principle")
        if role in ("explainer", "rater"):
            sub.add_argument("submission")
        if role == "explainer":
            sub.add_argument("--report", type=Path, help="a report.json with the submission as a target")
        if role in ("author", "judge"):
            sub.add_argument("--run", help="author: 1, 2, ...; judge: <model>-<run>")
        if role == "solver":
            sub.add_argument("--student", help="the package name, <ident>_<surname>")
            sub.add_argument("--absolute-imports", action="store_true")
        if role == "candidates":
            sub.add_argument("--count", type=int, default=6)
        sub.add_argument("--base", type=Path, default=HERE, help="the M6 directory")
        sub.add_argument("--pilot", type=Path, default=PILOT, help="the pilot directory")
        sub.add_argument("--out", type=Path, help=f"the stage directory (default under {ROOT})")
    back = commands.add_parser("collect")
    back.add_argument("stage", type=Path)
    back.add_argument("--force", action="store_true", help="replace an existing destination")
    back.add_argument("--model", help="explainer, rater: the agent's model, recorded with its output")
    args = parser.parse_args(argv)
    if args.role == "collect":
        print(collect(args.stage, args.force, args.model))
        return 0
    args.base, args.pilot = args.base.resolve(), args.pilot.resolve()
    if args.principle not in harness.PRINCIPLES:
        raise SystemExit(f"the principle must be one of {harness.PRINCIPLES}, not {args.principle!r}")
    if args.role == "candidates":
        print("\n".join(candidates(args)))
    else:
        print(stage(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
