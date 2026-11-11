"""Self-test of the M7 harness on fake agent outputs, in a temporary directory.

It builds a fake pilot as the pilot's self-test does (the catalogue's
variants as injected errors; the pilot's real ``assignment.md``, or a made-up
one with a principle's section for a principle the pilot lacks) and a fake
M6 (``results-vo3-vo5.md`` listing 6 explanations for the owner, with fake
explanations and ratings by ``opus``). Then, for every principle, it stages
all 12 solvers (``stage.py solver-novice``) and writes what each would: the
catalogue's first detected error variant for the students of the slots 1
and 2, ``ok_basic`` for the others; and all 36 judges (``stage.py judge``)
with fake verdicts: ``sonnet-1`` flags the slots 1-3, ``sonnet-2`` slot 1,
``haiku-1`` the slots 1-2. So the tool and the judges disagree on slots 2
and 3 of each principle. Then ``score.py`` (no forms yet), ``forms.py
review`` and ``vo5``, fake answers of the owner in part of both forms, and
``score.py`` again. It checks that

1. each stage holds exactly its inputs; the ``no-principle`` assignment is
   the pilot's without the principle's section and mentions no principle,
   the ``plain`` one is the pilot's unchanged; the student is the fixed one;
2. ``collect`` puts each output where ``score.py`` reads it, and refuses a
   solution that does not parse, a judge's verdict on another id and an
   existing destination without ``--force``; every collect, refusals and
   the ``--force`` replacement included, is a line of ``collect.log``;
3. ``review.md`` holds every flagged solution (slots 1-3 of each principle,
   slot 1 flagged by all) and 6 drawn from the rest, and is blind (no
   verdict, no judge run, no error id, no reason for the sample outside its
   header comment); ``--all`` puts every solution in it; ``owner_vo5.md``
   the 6 explanations and the rater's rubric; neither form is overwritten
   without ``--force``;
4. ``results.md`` has no empty cell and no ``–``; without answers every
   ground-truth cell is ``pending owner review`` (exit 0); with the answers
   the known counts (tool and judges on the natural violation and the clean
   one of the first principle, the second still pending; VO5 5/6 parts);
5. ``score.py`` exits 1 on a value out of range in either form, a form
   naming an unknown solution, a missing judgment, a missing meta file, a
   meta not of its student's slot, and on each strict-parse error (an answer
   under an empty field, a field twice, a heading twice, an item missing, the
   header line missing), naming the item; ``forms.py review`` exits 1 on a
   missing judgment;
5a. an unsampled solution the tool flags after the form was generated is
   listed under "Needs review: not in the form" and not counted; a group
   with no sampled solution reads ``none in the sample`` once the owner has
   answered everything, and a reviewed solution without a tool verdict
   shows ``1 no verdict``;
6. the README's dispatch list is ``stage.py plan encapsulation
   io_separation``;
7. the repository is left unchanged (``git status`` and every file's mtime).

Exits 0 when all hold. Usage, from the repository root::

    python example/principles/m7/selftest.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402

CATALOGUE = harness.CATALOGUE
ROOT = harness.REPO
STAGE_ONE = ("encapsulation", "io_separation")
FLAGS = {"sonnet-1": {0, 1, 2}, "sonnet-2": {0}, "haiku-1": {0, 1}}
ERRORS = {0, 1}


def _module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pilot_selftest = _module("pilot_selftest", harness.PILOT / "selftest.py")
stage_py = _module("m7_stage", HERE / "stage.py")


def _run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    done = subprocess.run(
        [sys.executable, str(HERE / script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"{script} {' '.join(args[:1])}: exit {done.returncode}")
    return done


class Harness:
    """The stages of one temporary M7 base, with the failures found."""

    def __init__(self, tmp: Path) -> None:
        self.tmp, self.base, self.pilot, self.m6 = (
            tmp,
            tmp / "m7",
            tmp / "pilot",
            tmp / "m6",
        )
        self.failures: list[str] = []
        self.count = 0
        self.collects: list[str] = []

    def stage(self, role: str, *args: str, expect: set[str]) -> Path:
        self.count += 1
        out = self.tmp / "stages" / f"{role}-{self.count}"
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            stage_py.main(
                [
                    role,
                    *args,
                    "--base",
                    str(self.base),
                    "--pilot",
                    str(self.pilot),
                    "--out",
                    str(out),
                ]
            )
        if Path(printed.getvalue().strip()) != out:
            raise SystemExit(f"stage.py {role} {args} printed {printed.getvalue()!r}")
        seen = {
            path.relative_to(out).as_posix()
            for path in out.rglob("*")
            if path.is_file()
        }
        if seen != expect:
            self.failures.append(
                f"the {role} stage holds {sorted(seen)}, not {sorted(expect)}"
            )
        return out

    def collect(self, out: Path, refused: bool = False, force: bool = False) -> None:
        self.collects.append(
            "refused" if refused else "replaced" if force else "placed"
        )
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                stage_py.main(["collect", str(out), *(["--force"] if force else [])])
        except SystemExit as error:
            if not refused:
                self.failures.append(f"collect {out.name} failed: {error}")
            return
        if refused:
            self.failures.append(f"collect accepted {out.name}, which it must refuse")

    def score(self) -> str:
        done = _run("score.py", "--base", str(self.base), "--m6", str(self.m6))
        if done.returncode != 0:
            self.failures.append(
                f"score.py exited {done.returncode}: {done.stderr[-1500:]}"
            )
        if "Traceback" in done.stderr:
            self.failures.append(f"score.py crashed: {done.stderr[-1500:]}")
        path = self.base / "results.md"
        return path.read_text(encoding="utf-8") if path.is_file() else ""


def _fake_pilot(h: Harness, principle: str) -> None:
    pilot_selftest._fake_submissions(CATALOGUE / principle, h.pilot / principle)
    real = harness.PILOT / principle / "assignment.md"
    text = (
        real.read_text(encoding="utf-8")
        if real.is_file()
        else "# Zadání\n\nNapište program.\n\n## Princip: Něco\n\nPopis principu.\n"
    )
    (h.pilot / principle / "assignment.md").write_text(text, encoding="utf-8")


def _fake_m6(h: Harness, principles: list[str]) -> list[str]:
    pools = {
        p: sorted(path.name for path in (h.pilot / p / "injected" / "err").iterdir())
        for p in principles
    }
    items: list[str] = []
    while len(items) < 6:
        for p in principles:
            if pools[p] and len(items) < 6:
                items.append(f"{p}/{pools[p].pop(0)}")
    for name in items:
        p, s = name.split("/", 1)
        folder = h.m6 / "results" / "explanations" / p
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{s}.md").write_text(f"Falešné vysvětlení {s}.\n", encoding="utf-8")
        (folder / f"{s}.json").write_text('{"model": "sonnet"}\n', encoding="utf-8")
        rating = {
            "location": 2,
            "principle": 2,
            "reason": 1,
            "comment": "",
            "model": "opus",
        }
        harness.write_json(h.m6 / "results" / "ratings" / p / f"{s}.json", rating)
    listing = "\n".join(
        f"- `{name}`: `results/explanations/{name}.md`" for name in items
    )
    (h.m6 / "results-vo3-vo5.md").write_text(
        f"# M6\n\n## VO5\n\nFor the owner's review (3 per principle, seed 7):\n\n{listing}\n\n"
        "## Realistic code\n",
        encoding="utf-8",
    )
    return items


def _solvers(h: Harness, principle: str) -> None:
    entry = pilot_selftest.load_entry(CATALOGUE / principle)
    error = next(e["example"] for e in entry.get("errors", []) if "gap" not in e)
    pilot_text = (h.pilot / principle / "assignment.md").read_text(encoding="utf-8")
    for index, (model, variant, run) in enumerate(harness.SLOTS):
        student = harness.NAMES[index]
        out = h.stage(
            "solver-novice",
            principle,
            "--model",
            model,
            "--variant",
            variant,
            "--run",
            str(run),
            expect={"assignment.md", "submission.txt"},
        )
        text = (out / "assignment.md").read_text(encoding="utf-8")
        if variant == "plain" and text != pilot_text:
            h.failures.append(
                f"{principle} {student}: the plain assignment is not the pilot's"
            )
        if variant == "no-principle" and (
            re.search(r"(?mi)^## Princip", text)
            or re.search(r"(?i)\bprincip", text)
            or len(text) >= len(pilot_text)
            or text.splitlines()[0] != pilot_text.splitlines()[0]
        ):
            h.failures.append(
                f"{principle} {student}: the no-principle assignment is wrong"
            )
        if f"`{student}/`" not in (out / "submission.txt").read_text(encoding="utf-8"):
            h.failures.append(f"{principle}: submission.txt does not name {student}")
        source = error if index in ERRORS else "ok_basic"
        shutil.copytree(
            CATALOGUE / principle / "assignments" / source,
            out / student,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        if index == 4:
            broken = out / student / "broken.py"
            broken.write_text("def (:\n", encoding="utf-8")
            h.collect(out, refused=True)
            broken.unlink()
        h.collect(out)
        if index == 4:
            h.collect(out, refused=True)
            h.collect(out, force=True)
        meta = harness.read_json(harness.meta_path(h.base, principle, student))
        if (meta["model"], meta["variant"], meta["run"]) != (model, variant, run):
            h.failures.append(f"the meta of {principle}/{student} is {meta}")


def _judges(h: Harness, principle: str) -> None:
    for run, flagged in FLAGS.items():
        for index, student in enumerate(harness.NAMES):
            out = h.stage(
                "judge",
                principle,
                student,
                "--run",
                run,
                expect={"assignment.md", f"whole/{student}.md"},
            )
            verdict = {
                "id": student,
                "violates": index in flagged,
                "reason": "falešný",
                "explanation": "",
            }
            if index == 0 and run == "sonnet-1":
                (out / "verdicts.json").write_text(
                    json.dumps([{**verdict, "id": "x"}]), encoding="utf-8"
                )
                h.collect(out, refused=True)
            (out / "verdicts.json").write_text(json.dumps([verdict]), encoding="utf-8")
            h.collect(out)


def _answer(path: Path, answers: dict[str, dict[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for name, fields in answers.items():
        head = text.index(f". `{name}`\n")
        end = text.find("\n## ", head)
        end = len(text) if end < 0 else end
        block = text[head:end]
        for key, value in fields.items():
            block = re.sub(rf"(?m)^{key}:.*$", f"{key}: {value}", block, count=1)
        text = text[:head] + block + text[end:]
    path.write_text(text, encoding="utf-8")


def _rows(results: str, section: str) -> dict[tuple[str, str], list[str]]:
    part = results.split(f"## {section}", 1)[1].split("\n## ", 1)[0]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in part.splitlines()
        if line.startswith("| ") and not line.startswith("| Principle")
    ]
    return {(row[0].strip("`"), row[1]): row[2:] for row in rows}


def _empty(h: Harness, results: str) -> None:
    h.failures += [
        f"empty cell: {line!r}"
        for line in results.splitlines()
        if line.startswith("| ") and re.search(r"\|\s*(–|-)?\s*(?=\|)", line[1:])
    ]


def _forms(h: Harness, principles: list[str], items: list[str]) -> None:
    common = ["--base", str(h.base), "--pilot", str(h.pilot)]
    if _run("forms.py", "review", *common).returncode != 0:
        h.failures.append("forms.py review failed")
        return
    path = h.base / "review.md"
    text = path.read_text(encoding="utf-8")
    listed = re.findall(r"(?m)^## \d+\. `([^`]+)`$", text)
    wrong = {f"{p}/{harness.NAMES[i]}" for p in principles for i in (0, 1, 2)} - set(
        listed
    )
    if len(listed) != 3 * len(principles) + 6 or wrong:
        h.failures.append(f"review.md lists {listed}; missing flagged {sorted(wrong)}")
    _blind(h, text, principles)
    if _run("forms.py", "review", *common).returncode == 0:
        h.failures.append("forms.py review overwrote review.md without --force")
    kept = path.read_bytes()
    if _run("forms.py", "review", *common, "--all", "--force").returncode != 0:
        h.failures.append("forms.py review --all failed")
    every = re.findall(r"(?m)^## \d+\. `([^`]+)`$", path.read_text(encoding="utf-8"))
    if len(every) != len(harness.NAMES) * len(principles):
        h.failures.append(f"forms.py review --all lists {len(every)} solutions")
    path.write_bytes(kept)
    if _run("forms.py", "vo5", *common, "--m6", str(h.m6)).returncode != 0:
        h.failures.append("forms.py vo5 failed")
        return
    vo5 = (h.base / "owner_vo5.md").read_text(encoding="utf-8")
    if (
        re.findall(r"(?m)^## \d+\. `([^`]+)`$", vo5) != items
        or "**location**" not in vo5
    ):
        h.failures.append(
            "owner_vo5.md does not list the 6 explanations with the rubric"
        )


def _blind(h: Harness, text: str, principles: list[str]) -> None:
    """No verdict, judge run, error id or sample reason outside the header."""
    visible = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    errors = {
        error
        for p in principles[:1]
        for verdict in harness.tool_verdicts(h.base, p).values()
        for error in verdict["errors"]
    }
    leaks = [
        word
        for word in (
            *harness.JUDGE_RUNS,
            "does not violate",
            "violates (",
            "no verdict",
            "disagreement",
            "- tool",
            "- judges",
            *errors,
        )
        if word in visible
    ]
    if leaks or not errors:
        h.failures.append(f"review.md is not blind: {leaks} (errors {errors})")


def _collect_log(h: Harness) -> None:
    path = stage_py.log_path(h.base)
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    outcomes = [line.split("\t")[4].split(":")[0] for line in lines]
    if outcomes != h.collects:
        h.failures.append(
            f"collect.log has {len(lines)} lines {sorted(set(outcomes))},"
            f" not the {len(h.collects)} collects"
        )
    forced = [line for line in lines if "\tcollect --force\t" in line]
    if len(forced) != h.collects.count("replaced") or any(
        not line.endswith("\treplaced") for line in forced
    ):
        h.failures.append(
            f"collect.log does not record the --force replacement: {forced}"
        )


def _check_pending(h: Harness, results: str, principles: list[str]) -> None:
    rows = _rows(results, "Against the owner's ground truth")
    for p in principles:
        if rows.get((p, "both"), [""])[0] != "pending owner review":
            h.failures.append(f"without answers, {p} is {rows.get((p, 'both'))}")
    if "| all | 6 explanations | 0/6 rated |" not in results:
        h.failures.append("without answers, VO5 is not 0/6 rated")


def _check_answered(h: Harness, results: str, principles: list[str]) -> None:
    first, second = principles[0], principles[1]
    truth = _rows(results, "Against the owner's ground truth")
    known = {
        (first, "both"): [
            "1/2 reviewed",
            "detects 1/1; FP 0/1",
            "detects 1/1; FP 1/1",
            "detects 0/1; FP 0/1",
            "detects 1/1; FP 0/1",
        ],
        (first, "plain"): [
            "1/1 reviewed",
            *["detects 1/1; FP n/a (no clean one)"] * 2,
            "detects 0/1; FP n/a (no clean one)",
            "detects 1/1; FP n/a (no clean one)",
        ],
        (second, "both"): ["pending owner review"] * 5,
    }
    for key, cells in known.items():
        if truth.get(key) != cells:
            h.failures.append(f"ground truth {key} is {truth.get(key)}, not {cells}")
    overview = _rows(results, "All solutions, per principle and variant").get(
        (first, "both")
    )
    if (
        overview is None
        or overview[0] != "12"
        or not overview[1].startswith("2/12")
        or overview[2:] != ["2/12", "3/12", "1/12", "2/12", "0/12", "2/12"]
    ):
        h.failures.append(f"the overview of {first} is {overview}")
    if "| 5/6 parts, 1/2 explanations all equal |" not in results:
        h.failures.append("VO5 is not 5/6 parts, 1/2 all equal")
    if "not in the sample" not in results:
        h.failures.append("no solution reads 'not in the sample'")


_HEAD = re.compile(r"(?m)^## \d+\. `([^`]+)`$")


def _before(marker: str) -> Any:
    """The item whose block holds the first ``marker`` of a form."""
    return lambda text: _HEAD.findall(text[: text.index(marker)])[-1]


def _breakages(h: Harness, principle: str) -> None:
    review, vo5 = h.base / "review.md", h.base / "owner_vo5.md"
    judgment = harness.judgment_path(h.base, "haiku-1", principle, harness.NAMES[5])
    meta = harness.meta_path(h.base, principle, harness.NAMES[6])
    first = lambda text: _HEAD.findall(text)[0]  # noqa: E731
    last = lambda text: _HEAD.findall(text)[-1]  # noqa: E731
    for what, path, change, named in (
        (
            "violates: maybe",
            review,
            lambda t: t.replace("violates: yes", "violates: maybe", 1),
            _before("violates: yes"),
        ),
        (
            "an unknown solution",
            review,
            lambda t: t.replace(f"/{harness.NAMES[1]}`", "/zzzz99_nobody`", 1),
            None,
        ),
        (
            "location: 3",
            vo5,
            lambda t: t.replace("location: 2", "location: 3", 1),
            _before("location: 2"),
        ),
        ("a missing judgment", judgment, None, None),
        ("a missing meta file", meta, None, None),
        (
            "a meta of another slot",
            meta,
            lambda t: t.replace('"model": "sonnet"', '"model": "opus"', 1),
            None,
        ),
        (
            "an answer under an empty violates:",
            review,
            lambda t: t.replace("violates:\nnote:", "violates:\nyes\nnote:", 1),
            _before("violates:\nnote:"),
        ),
        (
            "two violates: lines",
            review,
            lambda t: t.replace("violates:\n", "violates:\nviolates: no\n", 1),
            _before("violates:\n"),
        ),
        ("a heading twice", review, _twice, first),
        ("an item missing", review, lambda t: t[: t.rindex("\n## ")] + "\n", last),
        ("the header line missing", review, lambda t: t.split("\n", 1)[1], None),
        (
            "a VO5 answer under an empty field",
            vo5,
            lambda t: t.replace("reason:\nnote:", "reason:\n2\nnote:", 1),
            _before("reason:\nnote:"),
        ),
        (
            "a VO5 field twice",
            vo5,
            lambda t: t.replace("location:\n", "location:\nlocation: 1\n", 1),
            _before("location:\n"),
        ),
        (
            "a VO5 item missing",
            vo5,
            lambda t: t[: t.rindex("\n## ")] + "\n",
            last,
        ),
    ):
        kept = path.read_bytes()
        name = ""
        if change is None:
            path.unlink()
        else:
            text = kept.decode("utf-8")
            name = named(text) if named else ""
            path.write_text(change(text), encoding="utf-8")
        done = _run("score.py", "--base", str(h.base), "--m6", str(h.m6))
        if done.returncode != 1 or "Traceback" in done.stderr:
            h.failures.append(f"score.py exited {done.returncode}, not 1, on {what}")
        elif name and f"`{name}`" not in done.stderr and repr(name) not in done.stderr:
            h.failures.append(
                f"on {what}, score.py does not name {name}: {done.stderr}"
            )
        if what == "a missing judgment":
            done = _run(
                "forms.py",
                "review",
                "--base",
                str(h.base),
                "--pilot",
                str(h.pilot),
                "--force",
            )
            if done.returncode != 1:
                h.failures.append(
                    "forms.py review did not exit 1 on a missing judgment"
                )
        path.write_bytes(kept)


def _twice(text: str) -> str:
    """The form with its first item's heading once more, at the end."""
    return text + f"\n## 99. `{_HEAD.findall(text)[0]}`\n\nviolates:\nnote:\n"


def _stale(h: Harness, principle: str, error: str) -> None:
    """An unsampled solution the tool flags after the form was generated."""
    listed = re.findall(
        r"(?m)^## \d+\. `([^`]+)`$",
        (h.base / "review.md").read_text(encoding="utf-8"),
    )
    student = next(
        name for name in harness.NAMES[3:] if f"{principle}/{name}" not in listed
    )
    folder = harness.code_dir(h.base, principle) / student
    saved = h.tmp / "saved-code"
    shutil.copytree(folder, saved)
    shutil.rmtree(folder)
    shutil.copytree(
        CATALOGUE / principle / "assignments" / error,
        folder,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    results = h.score()
    name = f"{principle}/{student}"
    section = results.partition("## Needs review: not in the form")[2]
    truth = _rows(results, "Against the owner's ground truth").get((principle, "both"))
    if (
        f"`{name}`" not in section
        or "not in the form, needs review" not in results
        or truth is None
        or "1 needs review, not in the form" not in truth[0]
    ):
        h.failures.append(f"the stale {name} is not listed as needing review ({truth})")
    shutil.rmtree(folder)
    shutil.copytree(saved, folder)
    shutil.rmtree(saved)


def _cells(h: Harness) -> None:
    """``none in the sample`` and ``n no verdict``, on records made up here."""
    score_py = _module("m7_score", HERE / "score.py")

    def record(student: str, variant: str, tool: str) -> dict[str, Any]:
        return {
            "principle": "p",
            "student": student,
            "meta": {"variant": variant},
            "tool": {"verdict": tool, "errors": []},
            "judges": {"sonnet-1": False},
        }

    records = [
        record("a", "plain", "no verdict (x)"),
        record("b", "plain", harness.TOOL_PASSES),
        record("c", "no-principle", harness.TOOL_PASSES),
    ]
    truth = {
        "p/a": {"violates": True, "note": "", "tool": "", "why": ""},
        "p/b": {"violates": False, "note": "", "tool": "", "why": ""},
    }
    rows = _rows(
        "## T\n"
        + "\n".join(score_py.against_truth(records, truth, ("sonnet-1",), set())),
        "T",
    )
    if rows.get(("p", "no-principle"), [""])[0] != "none in the sample":
        h.failures.append(
            f"no sampled solution reads {rows.get(('p', 'no-principle'))}"
        )
    if not rows.get(("p", "plain"), ["", ""])[1].endswith("; 1 no verdict"):
        h.failures.append(
            f"the tool without a verdict reads {rows.get(('p', 'plain'))}"
        )
    truth["p/b"]["violates"] = None
    rows = _rows(
        "## T\n"
        + "\n".join(score_py.against_truth(records, truth, ("sonnet-1",), set())),
        "T",
    )
    if rows.get(("p", "no-principle"), [""])[0] != "pending owner review":
        h.failures.append("an unfinished form does not read pending owner review")


def _readme(h: Harness) -> None:
    done = _run("stage.py", "plan", *STAGE_ONE)
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    if "\n## Validity threats\n" not in readme:
        h.failures.append("the README has no section Validity threats")
    if done.returncode != 0 or done.stdout.strip() not in readme:
        h.failures.append(
            "the README's dispatch list is not `stage.py plan` of stage 1"
        )
    if (
        len(re.findall(r"(?m)^\| S\d+ ", done.stdout)) != 24
        or len(re.findall(r"(?m)^\| J\d+ ", done.stdout)) != 72
    ):
        h.failures.append("stage.py plan of stage 1 is not 24 solver and 72 judge runs")


def main() -> int:
    snapshot, status = pilot_selftest._snapshot(), pilot_selftest._git_status()
    principles = list(harness.principles())
    if len(principles) < 2:
        print("FAIL: the self-test needs two principles")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        h = Harness(Path(tmp))
        for principle in principles:
            _fake_pilot(h, principle)
        items = _fake_m6(h, principles)
        for principle in principles:
            _solvers(h, principle)
            _judges(h, principle)
        _collect_log(h)
        _check_pending(h, h.score(), principles)
        _forms(h, principles, items)
        _check_pending(h, h.score(), principles)
        first = principles[0]
        _answer(
            h.base / "review.md",
            {
                f"{first}/{harness.NAMES[1]}": {"violates": "yes"},
                f"{first}/{harness.NAMES[2]}": {"violates": "no", "note": "falešná"},
            },
        )
        _answer(
            h.base / "owner_vo5.md",
            {
                items[0]: {"location": "2", "principle": "2", "reason": "1"},
                items[1]: {
                    "location": "0",
                    "principle": "2",
                    "reason": "1",
                    "note": "falešná",
                },
            },
        )
        results = h.score()
        _empty(h, results)
        _check_answered(h, results, principles)
        if '`README.md`, section "Validity threats"' not in results:
            h.failures.append("results.md does not point to the validity threats")
        _breakages(h, first)
        entry = pilot_selftest.load_entry(CATALOGUE / first)
        _stale(h, first, next(e["example"] for e in entry["errors"] if "gap" not in e))
        _cells(h)
        _readme(h)
        failures = h.failures
    if pilot_selftest._snapshot() != snapshot or pilot_selftest._git_status() != status:
        failures.append("the repository changed")
    for failure in failures:
        print(f"FAIL: {failure}")
    print("selftest: " + ("FAILED" if failures else "OK"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
