"""Shared by ``stage.py`` and ``score.py`` of the M6 evaluation.

The layout of the M6 data, the pilot helpers both reuse (loaded from
``../pilot/`` under their own names, since this directory has its own
``stage.py`` and ``score.py``), and the one way both run the tool on a
directory of submissions: ``run_evaluation`` with a dynamic run (sandbox
``bwrap``), read with ``class_overview`` by the task's principle.

Layout under the M6 directory (``--base``, by default this one)::

    results/                                   versioned, small
      tasks/<p>/run-<N>/task.toml               the authors' tasks
      explanations/<p>/<submission>.md          the explainers' texts
      ratings/<p>/<submission>.json             the raters' scores
      judgments/<run>/<p>.json                  judges on the realistic code
    data/                                      not versioned (.gitignore)
      solutions/<p>/<ident_surname>/            the realistic solutions
      meta/<p>/<ident_surname>.json             how each was asked for
      findings/<p>/<submission>.json            what each explainer read
      reports/                                  the tool's reports
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parent
PILOT = CATALOGUE / "pilot"
# The principles M6 measured; principles added to the catalogue later have no M6 runs.
PRINCIPLES = ("encapsulation", "io_separation")
STUDENT = re.compile(r"^[a-z]{4}\d{2}_[a-z]+$")
IGNORE = shutil.ignore_patterns("__pycache__")


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The pilot's stage.py puts ../pilot and .. on sys.path and imports the
# pilot's prepare.py and score.py under those names.
pilot_stage = _load("pilot_stage", PILOT / "stage.py")
pilot_prepare: Any = sys.modules["prepare"]
pilot_score: Any = sys.modules["score"]
files = pilot_prepare.files


def example_task(principle: str) -> Path:
    """The principle's own task (``task.toml`` beside the reference)."""
    task = CATALOGUE / principle / "task.toml"
    if not task.is_file():
        raise SystemExit(f"{task} is missing: no such principle")
    return task.parent


def realistic(base: Path, principle: str) -> Path:
    return base / "data" / "solutions" / principle


def submission(base: Path, pilot: Path, principle: str, name: str) -> Path:
    """The code of submission ``name``: an injected error of the pilot
    (``<id>-<carrier_>``) or a realistic solution (``<ident_surname>``)."""
    found = [
        path
        for path in (
            pilot / principle / "injected" / "err" / name / "solution",
            realistic(base, principle) / name,
        )
        if path.is_dir()
    ]
    if len(found) != 1:
        raise SystemExit(
            f"{name!r} is {'no' if not found else 'more than one'} submission of {principle}"
            " (a pilot injected error or a realistic solution)"
        )
    return found[0]


def copy_code(source: Path, target: Path) -> None:
    shutil.copytree(source, target, ignore=IGNORE)


def evaluate(task: Path, targets_dir: Path, out: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    """Run the tool with ``task`` on every submission in ``targets_dir``;
    return the report and, per submission name, its ``class_overview`` row
    (``verdict``, ``errors``, maybe ``not_judged``)."""
    from pythonarchtesting.mcp_server import evaluation, reports

    out.mkdir(parents=True, exist_ok=True)
    run = evaluation.run_evaluation(
        str(task.resolve()), str(out.resolve()), targets_dir=str(targets_dir.resolve()), dynamic=True
    )
    rows: dict[str, dict[str, Any]] = {}
    offset = 0
    while True:
        overview = reports.class_overview(run["report_json"], offset=offset, limit=200)
        rows.update({row.pop("name"): row for row in overview["submissions_page"]})
        offset += 200
        if offset >= overview["submissions"]:
            return str(run["report_json"]), rows


def explain(report: str, target: str, principle: str) -> dict[str, Any]:
    from pythonarchtesting.mcp_server import reports

    return dict(reports.explain_target(report, target, principle=principle, limit=200))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def pilot_pool(pilot: Path, principle: str) -> dict[str, dict[str, Any]]:
    """The pilot data VO3 runs on: every injected error and neutral defect
    and every carrier, by a name usable as a directory -> ``{"kind", "id",
    "path"}`` (``kind`` ``err``, ``neutral`` or ``carrier``)."""
    key_path = pilot / principle / "key.json"
    if not key_path.is_file():
        raise SystemExit(f"{key_path} is missing; the pilot data is needed")
    key = read_json(key_path)
    pool: dict[str, dict[str, Any]] = {}
    carriers = sorted({item["carrier"] for item in key.values() if item.get("carrier")})
    by_label = {item["id"]: item for item in key.values() if item["kind"] == "solution"}
    for carrier in carriers:
        name = "carrier_" + re.sub(r"\W", "_", carrier)
        pool[name] = {"kind": "carrier", "id": carrier, "path": by_label[carrier]["path"]}
    for item in key.values():
        if item["kind"] in ("err", "neutral"):
            folder = Path(item["path"]).parent.name
            name = f"{item['kind']}_" + re.sub(r"\W", "_", folder)
            pool[name] = {"kind": item["kind"], "id": item["id"], "path": item["path"]}
    for name, item in pool.items():
        path = pilot / principle / item["path"]
        if not path.is_dir():
            raise SystemExit(f"{path} is missing (pool {name}); the pilot's unversioned data is needed")
    return dict(sorted(pool.items()))


def build_pool(pilot: Path, principle: str, out: Path) -> dict[str, dict[str, Any]]:
    """Copy the VO3 pool into ``out`` (one directory per name)."""
    pool = pilot_pool(pilot, principle)
    for name, item in pool.items():
        copy_code(pilot / principle / item["path"], out / name)
    return pool


def failed_by_violation(row: dict[str, Any]) -> bool:
    """A verdict on the code: failed, and not only for a missing entity
    (as the pilot's ``UNMATCHED``, that is no verdict on the principle)."""
    return row["verdict"] == "failed" and set(row["errors"]) != {"missing_required_entity"}


def unmatched(row: dict[str, Any]) -> bool:
    return row["verdict"] == "failed" and set(row["errors"]) == {"missing_required_entity"}


RATING_KEYS = ("location", "principle", "reason")


def rating_problems(path: Path) -> list[str]:
    """What is wrong with a rater's ``rating.json`` (empty when it is fine)."""
    try:
        rating = read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return [f"{path}: not readable JSON ({error})"]
    if not isinstance(rating, dict):
        return [f"{path}: not a JSON object"]
    problems = [
        f"{path}: {key} must be 0, 1 or 2"
        for key in RATING_KEYS
        if type(rating.get(key)) is not int or rating[key] not in (0, 1, 2)
    ]
    if not isinstance(rating.get("comment"), str):
        problems.append(f"{path}: comment must be a string")
    return problems
