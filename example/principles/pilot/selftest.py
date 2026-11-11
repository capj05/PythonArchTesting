"""Self-test of the pilot harness on fake data, in a temporary directory.

From the catalogue's own variants (``example/principles/<p>/assignments/``) it
builds, for every principle,

- three fake solutions: the model solution ``ok_basic`` as ``text/fake-1`` and
  ``skeleton/fake-1``, and ``text/fake-2``, ``ok_basic`` with every module
  raising on import (the tool cannot run it: ``not_run``);
- one fake injected error per catalogue error the tool detects (its example
  variant, carrier ``skeleton/fake-1``; a known gap is left out), one fake
  neutral defect per other neutral variant (carrier ``text/fake-1``), and one
  more defect, ``input_handling`` on ``skeleton/fake-1``: ``ok_basic`` with
  one function renamed (the tool finds no counterpart: ``UNMATCHED``);

then runs ``prepare.py``, ``run_tool.py``, one judge stage and its
``collect`` (``stage.py``) and, after writing two fake judge runs,
``score.py``, all with ``--base`` in the temporary directory. It checks that

1. the tool gives every fake submission the verdict ``verify.py`` gives its
   variant (and ``UNMATCHED`` / ``not_run`` to the two above), and the
   explanation ``verify.py`` composes for a detected error;
2. every batch holds at most 4 submissions, at most one per carrier family;
3. the judge stage holds exactly ``assignment.md`` and its batch, and
   ``collect`` puts the verdicts where ``score.py`` reads them;
4. ``results.md`` has no empty cell, and the tool's counts are the known
   ones: errors N/N, defects 0/N, clean solutions 0/2, unmatched 1, not run 1;
5. ``score.py`` exits 1 on a missing judge verdict, a judge file that is not a
   list, an entry without ``violates``, an id judged twice, and a stale hash;
6. the repository is left unchanged.

Exits 0 when all hold. Usage, from the repository root::

    python example/principles/pilot/selftest.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parent
ROOT = CATALOGUE.parent.parent
sys.path.insert(0, str(CATALOGUE))

from explain import explanation, first_failure, load_entry, run_catalogue  # noqa: E402

# Per principle, a function of ``ok_basic`` whose renaming leaves the tool no
# counterpart of a reference function (and nothing else failing).
_RENAMED = {"io_separation": "average", "encapsulation": "report", "polymorphism": "total_area", "strategy": "total"}
_NOT_RUN = "not run"
_UNMATCHED = "renamed"


def _snapshot() -> dict[str, tuple[int, int]]:
    """Every file under ``example/principles`` with its size and mtime."""
    return {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(CATALOGUE.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def _git_status() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout


def _run(script: str, base: Path, *args: str) -> int:
    completed = subprocess.run(
        [sys.executable, str(HERE / script), *args, "--base", str(base)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    print(f"{' '.join([script, *args])}: exit {completed.returncode}")
    if completed.returncode != 0:
        print(completed.stdout[-1500:] + completed.stderr[-1500:])
    return completed.returncode


def _expected(principle_dir: Path) -> dict[str, tuple[str, str | None]]:
    """Variant -> (verdict, explanation) as ``verify.py`` decides them."""
    entry = load_entry(principle_dir)
    results = run_catalogue(principle_dir)
    found: dict[str, tuple[str, str | None]] = {}
    for item in entry.get("neutral", []):
        failure = first_failure(results[item["example"]], None)
        found[item["example"]] = ("FAIL" if failure else "PASS", None)
    for error in entry.get("errors", []):
        marker = None if "gap" in error else error["detected_by"]
        failure = first_failure(results[error["example"]], marker)
        text = explanation(error, failure) if failure and marker else None
        found[error["example"]] = ("FAIL" if failure else "PASS", text)
    found[_UNMATCHED] = ("UNMATCHED", None)
    found[_NOT_RUN] = ("FAIL", None)
    return found


def _modules(package: Path) -> list[Path]:
    return sorted(path for path in package.rglob("*.py") if path.name != "__init__.py")


def _fake_submissions(principle_dir: Path, out: Path) -> dict[str, str]:
    """Copy the variants into the pilot layout; path in ``key.json`` -> variant."""
    entry = load_entry(principle_dir)
    variants = principle_dir / "assignments"
    ignore = shutil.ignore_patterns("__pycache__")
    origin: dict[str, str] = {}
    for variant in ("text", "skeleton"):
        path = f"solutions/{variant}/fake-1/solution"
        shutil.copytree(variants / "ok_basic", out / path, ignore=ignore)
        origin[path] = "ok_basic"
    path = "solutions/text/fake-2/solution"
    shutil.copytree(variants / "ok_basic", out / path, ignore=ignore)
    for module in _modules(out / path):
        module.write_text('raise RuntimeError("broken")\n' + module.read_text(encoding="utf-8"), encoding="utf-8")
    origin[path] = _NOT_RUN
    injected = [("err", error, "skeleton/fake-1") for error in entry.get("errors", []) if "gap" not in error]
    injected += [
        ("neutral", item, "text/fake-1")
        for item in entry.get("neutral", [])
        if item["example"] != "ok_basic"
    ]
    injected.append(("neutral", {"id": "input_handling", "example": "ok_basic"}, "skeleton/fake-1"))
    for kind, item, carrier in injected:
        folder = out / "injected" / kind / f"{item['id']}-{carrier.replace('/', '_')}"
        shutil.copytree(variants / item["example"], folder / "solution", ignore=ignore)
        meta = {"kind": kind, "id": item["id"], "carrier": carrier, "injector": "selftest"}
        (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        origin[f"injected/{kind}/{folder.name}/solution"] = item["example"]
    renamed = out / "injected/neutral/input_handling-skeleton_fake-1"
    pattern = re.compile(rf"\b{_RENAMED[principle_dir.name]}\b")
    for module in _modules(renamed / "solution"):
        module.write_text(pattern.sub("fluxcapacitor", module.read_text(encoding="utf-8")), encoding="utf-8")
    origin["injected/neutral/input_handling-skeleton_fake-1/solution"] = _UNMATCHED
    (out / "assignment.md").write_text("# Falešné zadání\n", encoding="utf-8")
    return origin


def _fake_verdicts(base: Path, principle: str) -> dict[str, list[list[dict[str, Any]]]]:
    """Two fake judge runs: ``fake-a`` flags the errors, ``fake-b`` one solution."""
    key = json.loads((base / principle / "key.json").read_text(encoding="utf-8"))
    batches = json.loads((base / principle / "batches.json").read_text(encoding="utf-8"))
    first_solution = next(n for n, item in key.items() if item["kind"] == "solution")
    runs: dict[str, Callable[[str], bool]] = {
        "fake-a": lambda n: key[n]["kind"] == "err",
        "fake-b": lambda n: n == first_solution,
    }
    return {
        run: [
            [{"id": n, "violates": violates(n), "reason": "falešný verdikt",
              "explanation": "Co: falešné. Proč: selftest."} for n in batch]
            for batch in batches
        ]
        for run, violates in runs.items()
    }


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _check_batches(base: Path, principle: str) -> list[str]:
    key = json.loads((base / principle / "key.json").read_text(encoding="utf-8"))
    batches = json.loads((base / principle / "batches.json").read_text(encoding="utf-8"))
    failures = []
    if sorted(n for batch in batches for n in batch) != sorted(key):
        failures.append(f"{principle}: the batches do not hold every submission once")
    for batch in batches:
        families = [key[n]["carrier"] or key[n]["id"] for n in batch]
        if len(batch) > 4 or len(families) != len(set(families)):
            failures.append(f"{principle}: batch {batch} breaks the batching rule")
    return failures


def _stage_judge(base: Path, principle: str, verdicts: list[dict[str, Any]], tmp: Path) -> list[str]:
    """Stage batch 1 of run ``fake-a`` for a judge, answer it, collect it."""
    out = tmp / "stage-judge"
    command = [sys.executable, str(HERE / "stage.py"), "judge", principle, "--batch", "1",
               "--run", "fake-a", "--base", str(base), "--out", str(out)]
    staged = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    print(f"stage.py judge: exit {staged.returncode}")
    if staged.returncode != 0 or Path(staged.stdout.strip()) != out:
        return [f"stage.py judge failed: {staged.stdout[-500:]}{staged.stderr[-1500:]}"]
    batch = json.loads((base / principle / "batches.json").read_text(encoding="utf-8"))[0]
    seen = {path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file()}
    wanted = {"assignment.md"} | {f"whole/{n}.md" for n in batch}
    failures = [] if seen == wanted else [f"the judge stage holds {sorted(seen)}, not {sorted(wanted)}"]
    _write(out / "verdicts.json", verdicts)
    back = subprocess.run([sys.executable, str(HERE / "stage.py"), "collect", str(out)],
                          cwd=ROOT, capture_output=True, text=True, check=False)
    print(f"stage.py collect: exit {back.returncode}")
    target = base / "judgments" / "fake-a" / f"{principle}-b1.json"
    if back.returncode != 0 or not target.is_file():
        return failures + [f"stage.py collect failed: {back.stderr[-1500:]}"]
    if json.loads(target.read_text(encoding="utf-8")) != verdicts:
        failures.append("collect changed the judge's verdicts")
    return failures


def _tool_column(results: str, principle: str) -> dict[str, str]:
    """Row label -> the tool's cell, in one principle's section of ``results.md``."""
    section = results.split(f"## `{principle}`", 1)[1].split("\n## ", 1)[0]
    rows = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 2:
            rows[cells[0]] = cells[1]
    return rows


def _known_counts(principle_dir: Path, total: int) -> dict[str, str]:
    entry = load_entry(principle_dir)
    errors = sum(1 for error in entry.get("errors", []) if "gap" not in error)
    defects = sum(1 for item in entry.get("neutral", []) if item["example"] != "ok_basic") + 1
    return {
        "vložené chyby označené": f"{errors}/{errors}",
        "rušivé vady označené (FP)": f"0/{defects}",
        "čistá řešení označená": "0/2",
        "nespárovaná": f"1/{total}",
        "nespuštěno": f"1/{total}",
        "vložené chyby označené, nosič čistý": f"{errors}/{errors}",
        "rušivé vady označené (FP), nosič čistý": f"0/{defects}",
    }


def _breakages(base: Path, principle: str) -> list[tuple[str, Path, Callable[[Any], Any]]]:
    """Faults ``score.py`` must refuse: (what, file, how to break its JSON)."""
    batch = base / "judgments" / "fake-b" / f"{principle}-b1.json"

    def stale(tool: dict[str, Any]) -> dict[str, Any]:
        first = next(iter(tool))
        return {**tool, first: {**tool[first], "sha256": "0" * 64}}

    return [
        ("a missing judge verdict", batch, lambda items: items[1:]),
        ("a judge file that is not a list", batch, lambda items: items[0]),
        ("an entry without violates", batch,
         lambda items: [{k: v for k, v in items[0].items() if k != "violates"}] + items[1:]),
        ("an id judged twice", batch, lambda items: items + items[:1]),
        ("a stale hash", base / principle / "tool.json", stale),
    ]


def main() -> int:
    snapshot, status = _snapshot(), _git_status()
    failures: list[str] = []
    principles = sorted(path.parent for path in CATALOGUE.glob("*/principle.toml"))
    missing = [p.name for p in principles if p.name not in _RENAMED]
    if missing:
        print(f"FAIL: no function to rename in {missing}; extend _RENAMED")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "pilot"
        origins = {p.name: _fake_submissions(p, base / p.name) for p in principles}
        expected = {p.name: _expected(p) for p in principles}
        if _run("prepare.py", base) or _run("run_tool.py", base):
            return 1
        for principle in origins:
            failures += _check_batches(base, principle)
            key = json.loads((base / principle / "key.json").read_text(encoding="utf-8"))
            tool = json.loads((base / principle / "tool.json").read_text(encoding="utf-8"))
            for neutral, item in key.items():
                variant = origins[principle][item["path"]]
                verdict, text = expected[principle][variant]
                got = tool[neutral]
                if got["verdict"] != verdict:
                    failures.append(f"{principle} {variant}: tool {got['verdict']}, verify {verdict}")
                if bool(got["not_run"]) != (variant == _NOT_RUN):
                    failures.append(f"{principle} {variant}: not_run is {got['not_run']}")
                if text is not None and text not in got["explanations"]:
                    failures.append(f"{principle} {variant}: explanation differs from verify.py")
        first = principles[0].name
        for principle in origins:
            for run, batches in _fake_verdicts(base, principle).items():
                for index, verdicts in enumerate(batches, start=1):
                    if (principle, run, index) == (first, "fake-a", 1):
                        failures += _stage_judge(base, principle, verdicts, Path(tmp))
                    else:
                        _write(base / "judgments" / run / f"{principle}-b{index}.json", verdicts)
        if _run("score.py", base):
            return 1
        results = (base / "results.md").read_text(encoding="utf-8")
        empty = [line for line in results.splitlines() if re.search(r"\|\s*(–\s*)?\|", line)]
        failures += [f"results.md: empty cell in {line!r}" for line in empty]
        for principle_dir in principles:
            total = len(json.loads((base / principle_dir.name / "key.json").read_text(encoding="utf-8")))
            got = _tool_column(results, principle_dir.name)
            for label, cell in _known_counts(principle_dir, total).items():
                if got.get(label) != cell:
                    failures.append(f"{principle_dir.name}: tool {label} is {got.get(label)}, not {cell}")
        for what, path, breaks in _breakages(base, first):
            good = path.read_text(encoding="utf-8")
            path.write_text(json.dumps(breaks(json.loads(good))), encoding="utf-8")
            if _run("score.py", base) != 1:
                failures.append(f"score.py did not exit 1 on {what}")
            path.write_text(good, encoding="utf-8")
    if _snapshot() != snapshot or _git_status() != status:
        failures.append("the repository changed")
    for failure in failures:
        print(f"FAIL: {failure}")
    print("selftest: " + ("FAILED" if failures else "OK"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
