"""Stage exactly the inputs one agent of the pilot may see, and collect its output.

Blinding by prompt alone is not enough: an agent told "read only X" can still
read the whole repository. So each agent works in a fresh directory that holds
nothing but its inputs, and writes its output there; ``collect`` copies that
output back into the pilot, validated.

``stage.py <role> <principle> [options]`` copies the inputs of ``role`` into
``<root>/<role>-<principle>-<n>/`` (``n`` the next free number; ``--out DIR``
instead) and prints that path:

============== ========================================== =========================
role           inputs in the stage directory               output it must write
============== ========================================== =========================
author         ``principle.txt`` (name, summary, why),     ``assignment.md``
               ``skeleton/``
solver-text    ``assignment.md``                           ``solution/`` (a package)
solver-skeleton ``assignment.md``, ``skeleton/``           ``solution/`` (a package)
injector-err   ``solution/`` (the carrier), ``error.txt``  ``solution/`` changed
               (the error's title and why)
injector-neutral ``solution/`` (the carrier),              ``solution/`` changed
               ``defect.txt`` (the defect, the principle's
               name and summary)
judge          ``assignment.md``, ``whole/wNNN.md`` of     ``verdicts.json``
               one batch
============== ========================================== =========================

Options: ``--run <model>-<run>`` (solvers, judge), ``--carrier
<variant>/<model>-<run>`` and ``--id`` (injectors), ``--batch N`` (judge,
1-based in ``batches.json``), ``--base DIR`` (the pilot directory).

What the stage is for (role, principle, run, ...) is kept next to it in
``<stage>.stage.json``, outside the agent's directory.
``stage.py collect <stage> [--injector <model>] [--force]`` reads it and copies
the output to

- author: ``<p>/assignment.md`` (not empty);
- solver: ``<p>/solutions/<variant>/<run>/solution/`` (a package whose every
  ``.py`` file parses);
- injector: ``<p>/injected/<kind>/<id>-<carrier_>/solution/`` (as a solver's,
  and different from the carrier) plus ``meta.json``, written by ``collect``
  with ``--injector``;
- judge: ``judgments/<run>/<p>-b<N>.json`` (a list with one valid entry per id
  of the batch, as ``score.py`` reads it).

An existing destination is replaced only with ``--force``.

Usage, from the repository root::

    python example/principles/pilot/stage.py judge io_separation --batch 1 --run sonnet-1
    python example/principles/pilot/stage.py collect <stage>
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(CATALOGUE))

from prepare import EXTRA_NEUTRAL, VARIANTS, carrier_dir, files  # noqa: E402
from score import judge_file, neutral_id  # noqa: E402
from explain import load_entry  # noqa: E402

ROOT = Path("/tmp/claude-1000/-home-jirka-git-PythonArchTesting/8173ba2d-10ce-4d65-89ca-58dad548b14d/scratchpad/stage")
ROLES = ("author", "solver-text", "solver-skeleton", "injector-err", "injector-neutral", "judge")
_RUN = re.compile(r"^[A-Za-z0-9]+-[A-Za-z0-9]+$")
_IGNORE = shutil.ignore_patterns("__pycache__")


def _entry(principle: str) -> dict[str, Any]:
    path = CATALOGUE / principle / "principle.toml"
    if not path.is_file():
        raise SystemExit(f"{path} is missing: no such principle")
    return load_entry(path.parent)


def _text(value: str) -> str:
    return " ".join(value.split())


def _need(path: Path) -> Path:
    if not path.exists():
        raise SystemExit(f"{path} is missing")
    return path


def _carrier(args: argparse.Namespace) -> str:
    carrier = args.carrier or ""
    variant, _, run = carrier.partition("/")
    if variant not in VARIANTS or not _RUN.match(run):
        raise SystemExit(f"--carrier must be <variant>/<model>-<run> with variant in {VARIANTS}, not {carrier!r}")
    return carrier


def _run(args: argparse.Namespace) -> str:
    if not args.run or not _RUN.match(args.run):
        raise SystemExit(f"--run must be <model>-<run>, not {args.run!r}")
    return str(args.run)


def _destination(args: argparse.Namespace) -> Path:
    if args.out is not None:
        out: Path = args.out.resolve()
        if out.exists() and any(out.iterdir()):
            raise SystemExit(f"{out} is not empty; a stage starts fresh")
        return out
    taken = [
        int(path.name.rsplit("-", 1)[1])
        for path in ROOT.glob(f"{args.role}-{args.principle}-*")
        if path.is_dir() and path.name.rsplit("-", 1)[1].isdigit()
    ]
    return ROOT / f"{args.role}-{args.principle}-{max(taken, default=0) + 1}"


def stage(args: argparse.Namespace) -> Path:
    """Copy the inputs of ``args.role`` into a fresh directory; return it."""
    base: Path = args.base.resolve()
    principle: str = args.principle
    entry = _entry(principle)
    pilot = base / principle
    manifest: dict[str, Any] = {"role": args.role, "principle": principle, "base": str(base)}
    inputs: dict[str, Path] = {}
    texts: dict[str, str] = {}
    if args.role == "author":
        texts["principle.txt"] = (
            f"Principle: {entry['name']}\n\nWhat it means:\n{_text(entry['summary'])}\n\n"
            f"Why it matters:\n{_text(entry['why'])}\n"
        )
        inputs["skeleton"] = _need(pilot / "skeleton")
    elif args.role in ("solver-text", "solver-skeleton"):
        manifest["run"] = _run(args)
        inputs["assignment.md"] = _need(pilot / "assignment.md")
        if args.role == "solver-skeleton":
            inputs["skeleton"] = _need(pilot / "skeleton")
    elif args.role in ("injector-err", "injector-neutral"):
        carrier = _carrier(args)
        kind = "err" if args.role == "injector-err" else "neutral"
        manifest.update(kind=kind, id=args.id, carrier=carrier)
        inputs["solution"] = _need(pilot / "solutions" / carrier / "solution")
        if kind == "err":
            errors = {error["id"]: error for error in entry.get("errors", [])}
            if args.id not in errors:
                raise SystemExit(f"--id must be one of {sorted(errors)}, not {args.id!r}")
            error = errors[args.id]
            texts["error.txt"] = f"Error: {error['title']}\n\nWhy it is an error:\n{_text(error['why'])}\n"
        else:
            defects = {item["id"]: item["title"] for item in entry.get("neutral", []) if item["id"] != "model_solution"}
            defects.update(EXTRA_NEUTRAL)
            if args.id not in defects:
                raise SystemExit(f"--id must be one of {sorted(defects)}, not {args.id!r}")
            texts["defect.txt"] = (
                f"Defect: {defects[args.id]}\n\nThe principle the change must not touch: "
                f"{entry['name']}\n{_text(entry['summary'])}\n"
            )
    elif args.role == "judge":
        manifest["run"] = _run(args)
        batches = json.loads(_need(pilot / "batches.json").read_text(encoding="utf-8"))
        if not isinstance(args.batch, int) or not 1 <= args.batch <= len(batches):
            raise SystemExit(f"--batch must be 1..{len(batches)}, not {args.batch!r}")
        manifest.update(batch=args.batch, ids=batches[args.batch - 1])
        inputs["assignment.md"] = _need(pilot / "assignment.md")
        for neutral in batches[args.batch - 1]:
            inputs[f"whole/{neutral}.md"] = _need(pilot / "whole" / f"{neutral}.md")
    out = _destination(args)
    out.mkdir(parents=True, exist_ok=True)
    for name, source in inputs.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, ignore=_IGNORE)
        else:
            shutil.copyfile(source, target)
    for name, text in texts.items():
        (out / name).write_text(text, encoding="utf-8")
    _manifest_path(out).write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def _manifest_path(out: Path) -> Path:
    return out.with_name(out.name + ".stage.json")


def _package(solution: Path) -> list[str]:
    """What is wrong with a submitted package (empty when it is fine)."""
    if not (solution / "__init__.py").is_file():
        return [f"{solution} is not a package (no __init__.py)"]
    problems = []
    for name, text in files(solution).items():
        try:
            ast.parse(text, filename=name)
        except SyntaxError as error:
            problems.append(f"{solution / name}: does not parse ({error.msg}, line {error.lineno})")
    return problems


def _place(source: Path, target: Path, force: bool) -> None:
    if target.exists():
        if not force:
            raise SystemExit(f"{target} exists; pass --force to replace it")
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, ignore=_IGNORE)
    else:
        shutil.copyfile(source, target)


def collect(out: Path, injector: str | None, force: bool) -> Path:
    """Validate a stage's output and copy it into the pilot; return where."""
    out = out.resolve()
    manifest = json.loads(_need(_manifest_path(out)).read_text(encoding="utf-8"))
    role, principle, base = manifest["role"], manifest["principle"], Path(manifest["base"])
    pilot = base / principle
    if role == "author":
        source = _need(out / "assignment.md")
        if not source.read_text(encoding="utf-8").strip():
            raise SystemExit(f"{source} is empty")
        target = pilot / "assignment.md"
    elif role in ("solver-text", "solver-skeleton"):
        source = _need(out / "solution")
        problems = _package(source)
        if problems:
            raise SystemExit("\n".join(problems))
        target = pilot / "solutions" / role.split("-", 1)[1] / manifest["run"] / "solution"
    elif role in ("injector-err", "injector-neutral"):
        if not injector or not _RUN.match(f"{injector}-0"):
            raise SystemExit("an injector's output needs --injector <model>")
        source = _need(out / "solution")
        problems = _package(source)
        carrier = pilot / "solutions" / manifest["carrier"] / "solution"
        if not problems and files(source) == files(carrier):
            problems.append(f"{source} is the carrier unchanged")
        if problems:
            raise SystemExit("\n".join(problems))
        folder = pilot / "injected" / manifest["kind"] / f"{manifest['id']}-{carrier_dir(manifest['carrier'])}"
        target = folder / "solution"
        if (folder / "meta.json").exists() and not force:
            raise SystemExit(f"{folder / 'meta.json'} exists; pass --force to replace it")
        _place(source, target, force)
        meta = {"kind": manifest["kind"], "id": manifest["id"], "carrier": manifest["carrier"], "injector": injector}
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False) + "\n", encoding="utf-8")
        return folder
    elif role == "judge":
        source = _need(out / "verdicts.json")
        problems: list[str] = []
        items = judge_file(source, problems)
        ids = [neutral_id(str(item["id"])) for item in items]
        expected = list(manifest["ids"])
        if not problems and sorted(ids) != sorted(expected):
            problems.append(f"{source}: the ids {sorted(ids)} are not the batch {sorted(expected)}")
        if problems:
            raise SystemExit("\n".join(problems))
        target = base / "judgments" / manifest["run"] / f"{principle}-b{manifest['batch']}.json"
    else:
        raise SystemExit(f"{_manifest_path(out)}: unknown role {role!r}")
    _place(source, target, force)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="role", required=True)
    for role in ROLES:
        sub = commands.add_parser(role)
        sub.add_argument("principle")
        sub.add_argument("--run")
        sub.add_argument("--carrier")
        sub.add_argument("--id")
        sub.add_argument("--batch", type=int)
        sub.add_argument("--base", type=Path, default=HERE, help="the pilot directory")
        sub.add_argument("--out", type=Path, help=f"the stage directory (default under {ROOT})")
    back = commands.add_parser("collect")
    back.add_argument("stage", type=Path)
    back.add_argument("--injector", help="the injector's model (injectors only)")
    back.add_argument("--force", action="store_true", help="replace an existing destination")
    args = parser.parse_args(argv)
    if args.role == "collect":
        print(collect(args.stage, args.injector, args.force))
    else:
        print(stage(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
