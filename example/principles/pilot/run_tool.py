"""Run the tool on every submission of the pilot and write ``<p>/tool.json``.

Each submission of ``<base>/<p>/key.json`` is checked against the principle's
reference with its markers::

    python-arch-test --source example/principles/<p>/reference --target <path>
        --format json --dynamic --sandbox bwrap

and gets ``{"verdict", "rules", "explanations", "not_run", "sha256"}``:

- ``verdict``: ``FAIL`` when a rule fails with a verdict on the code;
  ``UNMATCHED`` when the only failures are ``required_target_missing`` (the
  matching found no counterpart of a reference function; as in E1-E5 this is
  no verdict); ``PASS`` otherwise;
- ``rules``: the ``rule_id`` of every failed rule;
- ``explanations``: the student explanation of every failure with a verdict,
  composed from the catalogue by the same code as ``verify.py``
  (``../explain.py``); the catalogue error is chosen by ``choose_error``, from
  the facts of the catalogue's own example variants;
- ``not_run``: the failed rules that could not run the code (probe or case
  errors); they count as ``FAIL`` here, and ``score.py`` takes a submission
  with any of them out of the tool's rates;
- ``sha256``: the hash of the submission's ``whole/wNNN.md`` as rendered from
  the code the tool checked; ``score.py`` compares it with ``key.json``.

Usage, from the repository root::

    python example/principles/pilot/run_tool.py [--jobs 4] [--base DIR] [principle ...]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parent
sys.path.insert(0, str(CATALOGUE))

from prepare import files, sha256, whole  # noqa: E402
from explain import (  # noqa: E402  (the shared module lives one level up)
    CLI,
    NO_MATCH,
    choose_error,
    error_signatures,
    explanation,
    load_entry,
    run_catalogue,
)

_NOT_RUN = ("case_setup_failed", "reference_failed", "target_kind_mismatch")


def _did_not_run(result: dict[str, Any]) -> bool:
    reason = str((result.get("details") or {}).get("reason") or "")
    return result["status"] == "ERROR" or reason.startswith("probe_") or reason in _NOT_RUN


def check(reference: Path, target: Path) -> list[dict[str, Any]]:
    """The results of one tool run on one submission."""
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "report.json"
        command = [
            str(CLI),
            "--source", str(reference),
            "--target", str(target),
            "--format", "json", "--output", str(output),
            "--dynamic", "--sandbox", "bwrap",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode not in (0, 1) or not output.exists():
            raise SystemExit(
                f"the tool failed on {target} (exit {completed.returncode}):\n"
                f"{completed.stderr[-2000:]}"
            )
        report = json.loads(output.read_text(encoding="utf-8"))
    return [result for t in report["targets"] for result in t["results"]]


def verdict(results: list[dict[str, Any]], entry: dict, signatures: dict) -> dict[str, Any]:
    failed = [r for r in results if r["status"] in ("FAILED", "ERROR")]
    unmatched = [r for r in failed if (r.get("details") or {}).get("reason") == NO_MATCH]
    not_run = [r for r in failed if r not in unmatched and _did_not_run(r)]
    judged = [r for r in failed if r not in unmatched and r not in not_run]
    explanations: list[str] = []
    for result in judged:
        error = choose_error(entry, result, signatures)
        text = (
            explanation(error, result)
            if error is not None
            else f"**Co:** pravidlo `{result['rule_id']}` selhalo: {result.get('message', '')}"
        )
        if text not in explanations:
            explanations.append(text)
    if judged or not_run:
        decision = "FAIL"
    elif unmatched:
        decision = "UNMATCHED"
    else:
        decision = "PASS"
    return {
        "verdict": decision,
        "rules": sorted({r["rule_id"] for r in failed}),
        "explanations": explanations,
        "not_run": sorted({r["rule_id"] for r in not_run}),
    }


def run_principle(principle_dir: Path, jobs: int) -> dict[str, dict[str, Any]]:
    catalogue_dir = CATALOGUE / principle_dir.name
    entry = load_entry(catalogue_dir)
    signatures = error_signatures(entry, run_catalogue(catalogue_dir))
    key = json.loads((principle_dir / "key.json").read_text(encoding="utf-8"))
    reference = catalogue_dir / "reference"

    def one(neutral: str) -> tuple[str, dict[str, Any]]:
        target = principle_dir / key[neutral]["path"]
        found = verdict(check(reference, target), entry, signatures)
        found["sha256"] = sha256(whole(neutral, files(target)))
        return neutral, found

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return dict(sorted(pool.map(one, key)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--base", type=Path, default=HERE, help="the pilot directory")
    parser.add_argument("principle", nargs="*")
    args = parser.parse_args(argv)
    dirs = (
        [args.base / name for name in args.principle]
        if args.principle
        else sorted(path.parent for path in args.base.glob("*/key.json"))
    )
    if not dirs:
        raise SystemExit(f"no <principle>/key.json under {args.base}; run prepare.py")
    for principle_dir in dirs:
        verdicts = run_principle(principle_dir, args.jobs)
        (principle_dir / "tool.json").write_text(
            json.dumps(verdicts, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        counts = {name: 0 for name in ("FAIL", "PASS", "UNMATCHED")}
        for item in verdicts.values():
            counts[item["verdict"]] += 1
        print(f"{principle_dir.name}: " + ", ".join(f"{n} {k}" for k, n in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
