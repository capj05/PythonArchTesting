"""Shared by ``stage.py``, ``forms.py``, ``score.py`` and ``selftest.py`` of M7.

M7 is the second evaluation round (E2): natural violations in solutions that
"first-semester students" (agents, role ``solver-novice``) write, decided by
the tool, by LLM judges and, on a sample, by the owner.

This module holds the design (models, variants, runs and the fixed student
names), the M7 layout, the cut of the principle's section from an assignment,
and the one way the tool's verdicts are computed: always afresh, with the
current tool, over the stored solutions (they are never stored as data). It
reuses the M6 harness (``../m6/harness.py``, loaded as ``m6_harness``) and the
M6 stage (``../m6/stage.py``, loaded as ``m6_stage``), which in turn reuse the
pilot's helpers.

Layout under the M7 directory (``--base``, by default this one)::

    results/                                     versioned: the data
      code/<p>/<ident_surname>/                   the solutions
      meta/<p>/<ident_surname>.json               model, variant, run
      judgments/<run>/<p>/<ident_surname>.json    one judge on one solution
    review.md                                     the owner's ground truth
    owner_vo5.md                                  the owner's VO5 ratings
    results.md                                    written by score.py

The solutions live under ``results/code/`` and not under ``data/`` or
``solutions/``: the tool's verdicts are recomputed from them whenever the
tool changes, so they are data to keep (and ``m7/`` has no ``.gitignore``
entry).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parent
M6 = CATALOGUE / "m6"
REPO = CATALOGUE.parent.parent


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


m6: Any = _load("m6_harness", M6 / "harness.py")


def _load_m6(name: str, path: Path) -> ModuleType:
    """An M6 script as a module: it does ``import harness`` (its own), so it
    gets the M6 harness for the time of its import, and whatever ``harness``
    was (this module, when imported by that name) is put back."""
    saved = sys.modules.get("harness")
    sys.modules["harness"] = m6
    try:
        return _load(name, path)
    finally:
        if saved is None:
            del sys.modules["harness"]
        else:
            sys.modules["harness"] = saved


m6_stage: Any = _load_m6("m6_stage", M6 / "stage.py")
m6_score: Any = _load_m6("m6_score", M6 / "score.py")

ps: Any = m6.pilot_stage
PILOT: Path = m6.PILOT
STUDENT = m6.STUDENT
files = m6.files
copy_code = m6.copy_code
read_json = m6.read_json
write_json = m6.write_json

MODELS = ("haiku", "sonnet", "opus")
VARIANTS = ("plain", "no-principle")
RUNS = (1, 2)
JUDGE_RUNS = ("sonnet-1", "sonnet-2", "haiku-1")
STABILITY = ("sonnet-1", "sonnet-2")
REVIEW_SEED = 11

# One student per (model, variant, run), the same twelve for every principle
# (a class solves every task). None is a name of the demo (capj05_capsky,
# novj01_novak, dvop02_dvorak, svoe03_svoboda, kraj04_kral) or of M6.
NAMES = (
    "proa11_prochazka",
    "kucm12_kucera",
    "cerl13_cerna",
    "pokt14_pokorny",
    "marp15_marek",
    "posk16_pospisilova",
    "hajd17_hajek",
    "jele18_jelinek",
    "ruzv19_ruzicka",
    "benz20_benesova",
    "fial21_fiala",
    "sedo22_sedlacek",
)
SLOTS: tuple[tuple[str, str, int], ...] = tuple(
    (model, variant, run) for model in MODELS for variant in VARIANTS for run in RUNS
)
STUDENTS: dict[tuple[str, str, int], str] = dict(zip(SLOTS, NAMES))
assert len(SLOTS) == len(NAMES) and all(STUDENT.match(name) for name in NAMES)


def principles() -> tuple[str, ...]:
    """Every principle with ``principle.toml`` and ``task.toml`` beside it."""
    return tuple(
        sorted(
            path.parent.name
            for path in CATALOGUE.glob("*/principle.toml")
            if (path.parent / "task.toml").is_file()
        )
    )


def slot(student: str) -> tuple[str, str, int]:
    """The (model, variant, run) of a fixed student name."""
    for key, name in STUDENTS.items():
        if name == student:
            return key
    raise SystemExit(f"{student!r} is not one of the fixed students {NAMES}")


def code_dir(base: Path, principle: str) -> Path:
    return base / "results" / "code" / principle


def meta_path(base: Path, principle: str, student: str) -> Path:
    return base / "results" / "meta" / principle / f"{student}.json"


def judgment_path(base: Path, run: str, principle: str, student: str) -> Path:
    return base / "results" / "judgments" / run / principle / f"{student}.json"


def students(base: Path, principle: str) -> list[str]:
    """The collected solutions of a principle, by student name."""
    folder = code_dir(base, principle)
    return sorted(path.name for path in folder.glob("*") if path.is_dir())


def assignment(pilot: Path, principle: str) -> Path:
    """The assignment of a principle: the pilot's ``assignment.md``."""
    path = pilot / principle / "assignment.md"
    if not path.is_file():
        raise SystemExit(
            f"{path} is missing: the principle {principle} has no assignment"
            " (write it as the pilot's author does, then stage again)"
        )
    return path


_SECTION = re.compile(r"^##[ \t]+(?:Princip|Principle)\b[^\n]*$", re.M | re.I)
_NEXT = re.compile(r"^#{1,2}[ \t]", re.M)
_SENTENCE = re.compile(r"(?<=[.!?])[ \t]+")
_LEFT = re.compile(r"\bprincip", re.I)


def without_principle(text: str, source: str = "assignment.md") -> str:
    """The assignment without its section on the principle.

    The section is the one level-2 heading ``## Princip…`` or
    ``## Principle…`` with everything up to the next heading of level 1 or 2
    (or the end). The principle's name is what the heading says after a
    colon; any other sentence naming it (``Procvičíte princip **X**.``) is
    dropped too. Fails loudly when there is not exactly one such section, or
    when the rest still mentions a principle."""
    found = list(_SECTION.finditer(text))
    if len(found) != 1:
        raise SystemExit(
            f"{source}: {len(found)} sections '## Princip…' / '## Principle…', not 1;"
            " the principle's section cannot be cut"
        )
    head = found[0]
    following = _NEXT.search(text, head.end())
    end = following.start() if following else len(text)
    name = head.group(0).partition(":")[2].strip().strip("*").strip()
    before, after = text[: head.start()].rstrip(), text[end:].strip("\n")
    rest = f"{before}\n\n{after}" if after else before
    lines: list[str] = []
    for line in rest.splitlines():
        if name and name.lower() in line.lower():
            kept = [
                part
                for part in _SENTENCE.split(line)
                if name.lower() not in part.lower()
            ]
            line = " ".join(kept)
            if not line.strip():
                continue
        lines.append(line)
    cut = "\n".join(lines).strip() + "\n"
    left = [line for line in cut.splitlines() if _LEFT.search(line)]
    if left:
        raise SystemExit(
            f"{source}: without its principle's section it still mentions a"
            f" principle: {left[0]!r}"
        )
    return cut


TOOL_VIOLATES = "violates"
TOOL_PASSES = "does not violate"


def tool_verdict(row: dict[str, Any]) -> str:
    """``violates``, ``does not violate`` or ``no verdict (...)`` from a
    ``class_overview`` row; a failure only for a missing entity is no
    verdict on the principle (as in M6)."""
    if m6.failed_by_violation(row):
        return TOOL_VIOLATES
    if row["verdict"] == "passed":
        return TOOL_PASSES
    why = row.get("not_judged") or row.get("errors") or [row["verdict"]]
    return f"no verdict ({', '.join(why)})"


def tool_verdicts(base: Path, principle: str) -> dict[str, dict[str, Any]]:
    """The current tool on every solution of a principle (a copy of the
    solutions in a temporary directory; nothing is written under ``base``):
    student -> ``{"verdict": tool_verdict, "errors": [...]}``."""
    names = students(base, principle)
    if not names:
        return {}
    with tempfile.TemporaryDirectory() as tmp:
        targets = Path(tmp) / "targets"
        for name in names:
            copy_code(code_dir(base, principle) / name, targets / name)
        _, rows = m6.evaluate(m6.example_task(principle), targets, Path(tmp) / "out")
    missing = [name for name in names if name not in rows]
    if missing:
        raise SystemExit(f"{principle}: the tool's report has no {missing}")
    return {
        name: {
            "verdict": tool_verdict(rows[name]),
            "errors": list(rows[name]["errors"]),
        }
        for name in names
    }


def judgments(
    base: Path, principle: str, runs: tuple[str, ...], problems: list[str]
) -> dict[str, dict[str, bool]]:
    """run -> student -> violates, for every collected solution; each
    missing or malformed judgment goes to ``problems``."""
    found: dict[str, dict[str, bool]] = {}
    for run in runs:
        found[run] = {}
        for student in students(base, principle):
            path = judgment_path(base, run, principle, student)
            if not path.is_file():
                problems.append(f"{path} is missing (judge {run} on {student})")
                continue
            items = m6.pilot_score.judge_file(path, problems)
            if [str(item["id"]) for item in items] != [student]:
                problems.append(f"{path}: not one verdict on {student}")
                continue
            found[run][student] = bool(items[0]["violates"])
    return found


def shown(path: Path) -> str:
    """A path as the forms show it: relative to the repository when inside."""
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def dumps(data: Any) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"
