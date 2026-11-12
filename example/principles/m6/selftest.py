"""Self-test of the M6 harness on fake agent outputs, in a temporary directory.

It builds a fake pilot as the pilot's own self-test does (the catalogue's
variants as solutions, injected errors and defects; ``../pilot/prepare.py``
for ``key.json``), then, for every principle, runs each stage of
``stage.py`` with ``--out`` and ``--base`` in the temporary directory, writes
what the agent would and collects it:

- author run 1: the principle's own ``task.toml``, checked with the
  ``prepare`` command of the stage's ``tools.txt``; author run 2: a
  ``task.toml`` with a role bound to an entity that does not exist;
- solver: ``ok_basic`` under a student's name; for the first principle with
  ``--absolute-imports``, its relative imports made absolute and its
  ``__init__.py`` removed;
- explainer (the first of ``stage.py candidates``) and rater: a fake
  explanation and a fake rating, collected with different ``--model``;
- judge (``fake-1``): a fake verdict per solution;

then runs ``score.py`` (``--runs 2 --explanations 1 --solutions 2
--review 1``). It checks that

1. each stage holds exactly its inputs (the command lines of ``tools.txt``
   are ``tools.py describe|describe_marker|prepare`` with absolute paths; the
   explainer's ``findings.json`` has the verdict ``failed``; the explainer's
   and rater's ``principle.json`` hold ``name``, ``summary`` and ``why``);
2. ``collect`` puts each output where ``score.py`` reads it, and refuses a
   rating out of range, an explanation without ``--model``, a changed
   reference, and an absolute-import solution without such an import;
3. ``results-vo3-vo5.md`` has no empty cell; the example task and the copy of
   it (run 1, flagged as a copied example) flag every injected error as that
   error and nothing else (defects 0/N, carriers 0/N, unmatched 1: the
   renamed function), run 2 is not accepted; both realistic solutions pass;
   VO5 records both models;
4. ``score.py`` exits 1 on a missing rating, a missing explainer's model, a
   missing meta file, a missing run and no judge run;
5. the stages and the repository stay apart: the repository is left
   unchanged.

Exits 0 when all hold. Usage, from the repository root::

    python example/principles/m6/selftest.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parent
PILOT = CATALOGUE / "pilot"
ROOT = CATALOGUE.parent.parent

sys.path.insert(0, str(HERE))
from harness import PRINCIPLES  # noqa: E402


def _pilot_selftest() -> Any:
    spec = importlib.util.spec_from_file_location("pilot_selftest", PILOT / "selftest.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pilot_selftest = _pilot_selftest()


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, str(script), *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    print(f"{script.name} {' '.join(args[:2])}: exit {completed.returncode}")
    return completed


class Harness:
    """The stages of one temporary M6 base, with the failures found."""

    def __init__(self, tmp: Path) -> None:
        self.tmp, self.base, self.pilot = tmp, tmp / "m6", tmp / "pilot"
        self.failures: list[str] = []
        self.count = 0

    def stage(self, role: str, principle: str, *args: str, expect: set[str] | None = None) -> Path:
        self.count += 1
        out = self.tmp / "stages" / f"{role}-{self.count}"
        done = _run(HERE / "stage.py", role, principle, *args, "--base", str(self.base),
                    "--pilot", str(self.pilot), "--out", str(out))
        if done.returncode != 0 or Path(done.stdout.strip()) != out:
            raise SystemExit(f"stage.py {role} {principle} failed:\n{done.stdout[-800:]}{done.stderr[-1500:]}")
        seen = {path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file()}
        if expect is not None and seen != expect:
            self.failures.append(f"the {role} stage holds {sorted(seen)}, not {sorted(expect)}")
        return out

    def collect(self, out: Path, *args: str, refused: bool = False) -> Path | None:
        done = _run(HERE / "stage.py", "collect", str(out), *args)
        if refused:
            if done.returncode == 0:
                self.failures.append(f"collect accepted {out.name}, which it must refuse")
            return None
        if done.returncode != 0:
            self.failures.append(f"collect {out.name} failed: {done.stderr[-1500:]}")
            return None
        return Path(done.stdout.strip())

    def score(self, *args: str) -> int:
        done = _run(HERE / "score.py", "--runs", "2", "--explanations", "1", "--solutions", "2",
                    "--review", "1", "--base", str(self.base), "--pilot", str(self.pilot), *args)
        if done.returncode != 0:
            print(done.stderr[-2000:])
        if "Traceback" in done.stderr:
            self.failures.append(f"score.py {' '.join(args)} crashed")
        return done.returncode


def _package_files(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
            and "__pycache__" not in path.parts}


def _author(h: Harness, principle: str) -> None:
    reference = {f"task/reference/{name}" for name in _package_files(CATALOGUE / principle / "reference")}
    task_toml = (CATALOGUE / principle / "task.toml").read_text(encoding="utf-8")
    out = h.stage("author", principle, "--run", "1", expect={"principle.json", "tools.txt", *reference})
    tools = [line for line in (out / "tools.txt").read_text(encoding="utf-8").splitlines()
             if not line.startswith("#")]
    wanted = [f"{sys.executable} {HERE / 'tools.py'} describe {principle}",
              f"{sys.executable} {HERE / 'tools.py'} describe_marker <name>",
              f"{sys.executable} {HERE / 'tools.py'} prepare {out / 'task'}"]
    if tools != wanted:
        h.failures.append(f"tools.txt is {tools}, not {wanted}")
    described = (out / "tools.txt").read_text(encoding="utf-8")
    if "# describe_marker(name):" not in described or '"$new"' not in described:
        h.failures.append("tools.txt lacks describe_marker or the case language of prepare_task")
    marker = subprocess.run([*tools[1].split(" ")[:-1], "forbid_foreign_writes"], cwd=out,
                            capture_output=True, text=True, check=False)
    if "$new" not in marker.stdout:
        h.failures.append(f"the describe_marker command of tools.txt does not show $new: {marker.stdout[:300]}")
    if json.loads((out / "principle.json").read_text(encoding="utf-8")).get("id") != principle:
        h.failures.append("principle.json is not the principle's describe_principle")
    (out / "task" / "task.toml").write_text(task_toml, encoding="utf-8")
    prepared = subprocess.run(tools[2].split(" "), cwd=out, capture_output=True, text=True, check=False)
    if '"accepted": true' not in prepared.stdout:
        h.failures.append(f"the prepare command of tools.txt did not accept the task: {prepared.stdout[:500]}")
    h.collect(out)
    out = h.stage("author", principle, "--run", "2")
    broken = re.sub(r"(?m)^(\w+) = \[.*\]$", r'\1 = ["nosuch.function"]', task_toml, count=1)
    (out / "task" / "task.toml").write_text(broken, encoding="utf-8")
    (out / "task" / "reference" / "extra.py").write_text("X = 1\n", encoding="utf-8")
    h.collect(out, refused=True)
    (out / "task" / "reference" / "extra.py").unlink()
    h.collect(out)


def _solver(h: Harness, principle: str, student: str, absolute: bool) -> None:
    args = ["--student", student] + (["--absolute-imports"] if absolute else [])
    out = h.stage("solver", principle, *args, expect={"assignment.md", "submission.txt"})
    text = (out / "submission.txt").read_text(encoding="utf-8")
    if student not in text or ("overrides the import style" in text) != absolute:
        h.failures.append(f"submission.txt does not fit {args}: {text!r}")
    package = out / student
    shutil.copytree(CATALOGUE / principle / "assignments" / "ok_basic", package,
                    ignore=shutil.ignore_patterns("__pycache__"))
    if absolute:
        (package / "__init__.py").unlink()
        h.collect(out, refused=True)
        for module in package.glob("*.py"):
            module.write_text(re.sub(r"from \.(\w+) import", r"from \1 import",
                                     module.read_text(encoding="utf-8")), encoding="utf-8")
    h.collect(out)


def _explained(h: Harness, principle: str) -> None:
    done = _run(HERE / "stage.py", "candidates", principle, "--count", "1",
                "--base", str(h.base), "--pilot", str(h.pilot))
    submission = done.stdout.strip()
    if done.returncode != 0 or not submission:
        raise SystemExit(f"stage.py candidates failed: {done.stderr[-1500:]}")
    code = {f"code/{name}" for name in _package_files(h.pilot / principle / "injected" / "err" / submission / "solution")}
    out = h.stage("explainer", principle, submission, expect={"principle.json", "findings.json", *code})
    if not out.with_name(out.name + ".report").is_dir():
        h.failures.append(f"the explainer's report is not beside its stage {out}")
    findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
    if findings.get("verdict") != "failed" or not findings.get("findings"):
        h.failures.append(f"findings.json of {submission} has no failure: {findings}")
    if set(json.loads((out / "principle.json").read_text(encoding="utf-8"))) != {"name", "summary", "why"}:
        h.failures.append("the explainer's principle.json is not name, summary and why")
    (out / "explanation.md").write_text(f"Fake explanation of {submission}.\n", encoding="utf-8")
    h.collect(out, refused=True)
    h.collect(out, "--model", "fake-explainer")
    out = h.stage("rater", principle, submission, expect={"principle.json", "explanation.md", "rubric.md", *code})
    (out / "rating.json").write_text(json.dumps({"location": 3, "principle": 1, "reason": 1, "comment": ""}),
                                     encoding="utf-8")
    h.collect(out, "--model", "fake-rater", refused=True)
    (out / "rating.json").write_text(json.dumps({"location": 2, "principle": 1, "reason": 0, "comment": "fake"}),
                                     encoding="utf-8")
    h.collect(out, "--model", "fake-rater")


def _judge(h: Harness, principle: str, student: str) -> None:
    out = h.stage("judge", principle, "--run", "fake-1", expect={"assignment.md", f"whole/{student}.md"})
    verdicts = [{"id": student, "violates": False, "reason": "fake", "explanation": ""}]
    (out / "verdicts.json").write_text(json.dumps(verdicts), encoding="utf-8")
    h.collect(out)


def _rows(results: str, section: str) -> list[list[str]]:
    part = results.split(f"## {section}", 1)[1].split("\n## ", 1)[0]
    return [[cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in part.splitlines() if line.startswith("| ") and not line.startswith("| Principle")]


def _check_results(h: Harness, students: dict[str, str]) -> None:
    results = (h.base / "results-vo3-vo5.md").read_text(encoding="utf-8")
    h.failures += [f"empty cell: {line!r}" for line in results.splitlines()
                   if line.startswith("| ") and re.search(r"\|\s*(–|-)?\s*(?=\|)", line[1:])]
    if not (h.base / "results-vo3-vo5.csv").is_file():
        h.failures.append("results-vo3-vo5.csv is missing")
    rows = {(row[0].strip("`"), row[1]): row[2:] for row in _rows(results, "VO3")}
    for principle in students:
        entry = pilot_selftest.load_entry(CATALOGUE / principle)
        errors = sum(1 for error in entry.get("errors", []) if "gap" not in error)
        defects = sum(1 for item in entry.get("neutral", []) if item["example"] != "ok_basic") + 1
        total = errors + defects + 2
        # Every injected error (its example variant) is flagged as that error
        # and nothing else: a classification lost to another error fails here.
        known = [f"{errors}/{errors}", f"{errors}/{errors}", f"0/{defects}", "0/2", f"1/{total}", f"0/{total}"]
        for label, copied in (("example", "n/a"), ("run-1", "yes")):
            if rows.get((principle, label)) != ["yes", "0", copied, *known]:
                h.failures.append(f"VO3 {principle} {label} is {rows.get((principle, label))},"
                                  f" not {['yes', '0', copied, *known]}")
        run2 = rows.get((principle, "run-2")) or []
        if run2[:1] != ["no"] or run2[2:3] != ["no"]:
            h.failures.append(f"VO3 {principle} run-2 is {run2}, not accepted 'no', copied 'no'")
    real = {row[1]: row for row in _rows(results, "Realistic code")}
    for principle, student in students.items():
        if real.get(student, [""] * 5)[4] != "passed":
            h.failures.append(f"realistic {student} is {real.get(student)}, not passed")
    vo5 = _rows(results, "VO5")
    if len(vo5) != len(students) + 1 or vo5[-1][0] != "mean" or any(row[6:9] != ["fake-explainer", "fake-rater", "no"]
                                                      for row in vo5[:-1]):
        h.failures.append(f"VO5 rows are {vo5}")


def _breakages(h: Harness) -> None:
    rating = next((h.base / "results" / "ratings").glob("*/*.json"))
    model = next((h.base / "results" / "explanations").glob("*/*.json"))
    meta = next((h.base / "data" / "meta").glob("*/*.json"))
    for what, path in (("a missing rating", rating), ("a missing explainer's model", model),
                       ("a missing meta file", meta)):
        kept = path.read_bytes()
        path.unlink()
        if h.score() != 1:
            h.failures.append(f"score.py did not exit 1 on {what}")
        path.write_bytes(kept)
    if h.score("--runs", "3") != 1:
        h.failures.append("score.py did not exit 1 on a missing run")
    judgments = h.base / "results" / "judgments"
    judgments.rename(h.tmp / "judgments-away")
    if h.score() != 1:
        h.failures.append("score.py did not exit 1 without a judge run")
    (h.tmp / "judgments-away").rename(judgments)


def main() -> int:
    snapshot, status = pilot_selftest._snapshot(), pilot_selftest._git_status()
    principles = list(PRINCIPLES)
    students = {principle: f"test{index:02d}_novak" for index, principle in enumerate(principles, start=1)}
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(Path(tmp))
        for principle in principles:
            pilot_selftest._fake_submissions(CATALOGUE / principle, h.pilot / principle)
        if _run(PILOT / "prepare.py", "--base", str(h.pilot)).returncode != 0:
            return 1
        for index, principle in enumerate(principles):
            _author(h, principle)
            _solver(h, principle, students[principle], absolute=index == 0)
            _explained(h, principle)
            _judge(h, principle, students[principle])
        expected = {
            f"results/tasks/{p}/run-{n}/task.toml" for p in principles for n in (1, 2)
        } | {f"results/judgments/fake-1/{p}.json" for p in principles}
        found = {path.relative_to(h.base).as_posix() for path in (h.base / "results").rglob("*") if path.is_file()}
        if not expected <= found or len(found) != len(expected) + 3 * len(principles):
            h.failures.append(f"results/ holds {sorted(found)}")
        if h.score() != 0:
            h.failures.append("score.py failed on the complete data")
        else:
            _check_results(h, students)
            _breakages(h)
        failures = h.failures
    if pilot_selftest._snapshot() != snapshot or pilot_selftest._git_status() != status:
        failures.append("the repository changed")
    for failure in failures:
        print(f"FAIL: {failure}")
    print("selftest: " + ("FAILED" if failures else "OK"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
