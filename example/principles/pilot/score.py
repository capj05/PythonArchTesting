"""Score the pilot: the tool and every judge run on the same submissions.

Reads, per principle, ``<p>/key.json`` (what each neutral id is),
``<p>/tool.json`` (``run_tool.py``) and ``judgments/<run>/<p>-b<N>.json``
(``[{"id": "wNNN", "violates": true|false, "reason", "explanation"}]``), and
writes ``results.md`` and ``results.csv`` next to this file (or ``--base``).

Per principle, one row per measure and one column per decider (the tool and
each judge run):

- injected errors flagged (detection, x/N);
- injected neutral defects flagged (false positives, x/N);
- clean solutions flagged (x/N);
- unmatched (x/N): the tool's ``UNMATCHED``; a judge always decides, so 0;
- not run (x/N): the tool could not run the code (``not_run`` in
  ``tool.json``); a judge always decides, so 0;
- detection and false positives again, counted only over the injected
  variants whose carrier this decider considers clean (the tool ``PASS``, a
  judge ``violates: false``), so that a decider is not credited with flagging
  a variant for what its carrier already did.

The tool flags a submission when its verdict is ``FAIL`` (``UNMATCHED`` is no
verdict, as in E1-E5); a judge when it says ``violates: true``. A submission
the tool did not run is left out of the tool's numerators and denominators.
Then each carrier gets every decider's verdict, and every solution anyone
flags is listed, the candidates for natural violations to be checked by hand.
``results.csv`` has one row per submission.

Exits 1, writing nothing, when ``tool.json`` or a judge's verdict on some
submission is missing, when a judge file is malformed (not a list, an entry
without ``id`` / ``violates`` / ``reason`` / ``explanation``, an id twice in
one run), or when the ``sha256`` of a submission differs between
``key.json``, ``tool.json`` and ``whole/wNNN.md`` (if present): stale data.

Usage, from the repository root::

    python example/principles/pilot/score.py [--base DIR]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TOOL = "nástroj"
MEASURES = (
    ("err", "vložené chyby označené"),
    ("neutral", "rušivé vady označené (FP)"),
    ("solution", "čistá řešení označená"),
    ("unmatched", "nespárovaná"),
    ("not_run", "nespuštěno"),
)
CLEAN_CARRIER = (
    ("err", "vložené chyby označené, nosič čistý"),
    ("neutral", "rušivé vady označené (FP), nosič čistý"),
)
_JUDGE_KEYS = {"id": str, "violates": bool, "reason": str, "explanation": str}


def neutral_id(value: str) -> str:
    """A neutral id as written in the key: ``w7`` and ``w007`` are one."""
    letter, digits = value[:1], value[1:]
    return f"{letter}{int(digits):03d}" if digits.isdigit() else value


def judge_file(path: Path, problems: list[str]) -> list[dict[str, Any]]:
    """The valid entries of one judge file; every fault goes to ``problems``."""
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        problems.append(f"{path}: not readable JSON ({error})")
        return []
    if not isinstance(items, list):
        problems.append(f"{path}: not a JSON list")
        return []
    valid = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            problems.append(f"{path}: entry {index} is not an object")
            continue
        faults = [
            f"{name} is missing" if name not in item else f"{name} is not {kind.__name__}"
            for name, kind in _JUDGE_KEYS.items()
            if not isinstance(item.get(name), kind)
        ]
        if faults:
            problems.append(f"{path}: entry {index} ({item.get('id')!r}): " + ", ".join(faults))
            continue
        valid.append(item)
    return valid


def _judgments(base: Path, problems: list[str]) -> dict[str, dict[str, dict[str, Any]]]:
    """run -> {"<p>/wNNN": verdict item}."""
    runs: dict[str, dict[str, dict[str, Any]]] = {}
    for run_dir in sorted(path for path in (base / "judgments").glob("*") if path.is_dir()):
        found: dict[str, dict[str, Any]] = {}
        for path in sorted(run_dir.glob("*-b*.json")):
            principle = path.stem.rsplit("-b", 1)[0]
            for item in judge_file(path, problems):
                name = f"{principle}/{neutral_id(item['id'])}"
                if name in found:
                    problems.append(f"judge {run_dir.name}: {name} judged twice ({path.name})")
                    continue
                found[name] = item
        runs[run_dir.name] = found
    return runs


def _stale(principle_dir: Path, key: dict[str, Any], tool: dict[str, Any]) -> list[str]:
    """The submissions whose hash differs between the key, the tool and ``whole/``."""
    problems = []
    for neutral, item in key.items():
        stored = item.get("sha256")
        if not stored:
            problems.append(f"{principle_dir.name}/{neutral}: key.json has no sha256; rerun prepare.py")
            continue
        if neutral in tool and tool[neutral].get("sha256") != stored:
            problems.append(f"{principle_dir.name}/{neutral}: tool.json was made from other code; rerun run_tool.py")
        whole = principle_dir / "whole" / f"{neutral}.md"
        if whole.is_file() and hashlib.sha256(whole.read_bytes()).hexdigest() != stored:
            problems.append(f"{principle_dir.name}/{neutral}: whole/{neutral}.md differs from key.json")
    return problems


def _rate(hits: int, total: int) -> str:
    return f"{hits}/{total}"


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "/")


def _load(base: Path, problems: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    keys: dict[str, dict[str, Any]] = {}
    tools: dict[str, dict[str, Any]] = {}
    for key_path in sorted(base.glob("*/key.json")):
        principle = key_path.parent.name
        keys[principle] = json.loads(key_path.read_text(encoding="utf-8"))
        tool_path = key_path.parent / "tool.json"
        if not tool_path.is_file():
            problems.append(f"{tool_path} is missing; run run_tool.py")
            tools[principle] = {}
        else:
            tools[principle] = json.loads(tool_path.read_text(encoding="utf-8"))
            problems += [f"{tool_path}: no verdict on {n}" for n in keys[principle] if n not in tools[principle]]
        problems += _stale(key_path.parent, keys[principle], tools[principle])
    if not keys:
        problems.append(f"no <principle>/key.json under {base}; run prepare.py")
    return keys, tools


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, default=HERE, help="the pilot directory")
    args = parser.parse_args(argv)
    base: Path = args.base
    problems: list[str] = []
    keys, tools = _load(base, problems)
    runs = _judgments(base, problems)
    if not runs:
        problems.append(f"no judge run under {base / 'judgments'}")
    every = {f"{p}/{n}" for p, key in keys.items() for n in key}
    for run, verdicts in runs.items():
        problems += [f"judge {run}: no verdict on {n}" for n in sorted(every - set(verdicts))]
        problems += [f"judge {run}: {n} is in no key" for n in sorted(set(verdicts) - every)]
    if problems:
        for problem in problems[:40]:
            print(problem, file=sys.stderr)
        if len(problems) > 40:
            print(f"... and {len(problems) - 40} more", file=sys.stderr)
        return 1

    deciders = [TOOL] + [f"soudce {run}" for run in runs]

    def not_run(principle: str, neutral: str) -> bool:
        return bool(tools[principle][neutral].get("not_run"))

    def flags(principle: str, neutral: str) -> dict[str, bool]:
        tool = tools[principle][neutral]
        found = {TOOL: tool["verdict"] == "FAIL" and not not_run(principle, neutral)}
        for run, verdicts in runs.items():
            found[f"soudce {run}"] = verdicts[f"{principle}/{neutral}"]["violates"]
        return found

    def state(principle: str, neutral: str, decider: str) -> str:
        if decider == TOOL:
            return "nespuštěno" if not_run(principle, neutral) else tools[principle][neutral]["verdict"]
        return "porušuje" if flags(principle, neutral)[decider] else "neporušuje"

    def clean(principle: str, neutral: str, decider: str) -> bool:
        """Whether this decider considers the submission clean."""
        if decider == TOOL:
            return state(principle, neutral, TOOL) == "PASS"
        return not flags(principle, neutral)[decider]

    def counted(principle: str, neutral: str, decider: str) -> bool:
        return decider != TOOL or not not_run(principle, neutral)

    lines = [
        "# Pilot evaluace principů: nástroj a LLM soudci",
        "",
        "Vygenerováno skriptem `score.py`; neupravovat ručně. Označeno = nástroj `FAIL`"
        " (`UNMATCHED` se nepočítá), soudce `violates: true`.",
        "",
    ]
    rows: list[dict[str, Any]] = []
    candidates: list[str] = []
    for principle, key in keys.items():
        lines += [f"## `{principle}`", "", "| Míra | " + " | ".join(deciders) + " |",
                  "|---|" + "---|" * len(deciders)]
        flagged = {neutral: flags(principle, neutral) for neutral in key}
        by_label = {item["id"]: neutral for neutral, item in key.items() if item["kind"] == "solution"}
        for kind, label in MEASURES:
            cells = []
            for decider in deciders:
                if kind in ("unmatched", "not_run"):
                    wanted = "UNMATCHED" if kind == "unmatched" else "nespuštěno"
                    hits = sum(1 for n in key if state(principle, n, TOOL) == wanted) if decider == TOOL else 0
                    total = len(key)
                else:
                    chosen = [n for n in key if key[n]["kind"] == kind and counted(principle, n, decider)]
                    hits = sum(1 for n in chosen if flagged[n][decider])
                    total = len(chosen)
                cells.append(_rate(hits, total))
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        for kind, label in CLEAN_CARRIER:
            cells = []
            for decider in deciders:
                chosen = [
                    n for n in key
                    if key[n]["kind"] == kind and counted(principle, n, decider)
                    and clean(principle, by_label[key[n]["carrier"]], decider)
                ]
                cells.append(_rate(sum(1 for n in chosen if flagged[n][decider]), len(chosen)))
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        lines += [
            "",
            "Nástroj: odevzdání, na kterých některé pravidlo kód nespustilo (`not_run`, řádek"
            " „nespuštěno“), nejsou v čitatelích ani jmenovatelích nástroje. Řádky „nosič čistý“"
            " počítají jen vložené varianty, jejichž nosič daný rozhodující považuje za čistý"
            " (nástroj `PASS`, soudce `violates: false`); jmenovatel je za lomítkem.",
            "",
            "| Nosič | Odevzdání | " + " | ".join(deciders) + " |",
            "|---|---|" + "---|" * len(deciders),
        ]
        for carrier in sorted({item["carrier"] for item in key.values() if item["carrier"]}):
            neutral = by_label[carrier]
            verdicts = [state(principle, neutral, decider) for decider in deciders]
            lines.append(f"| {carrier} | {neutral} | " + " | ".join(verdicts) + " |")
        lines.append("")
        for neutral, item in key.items():
            tool = tools[principle][neutral]
            row = {
                "principle": principle,
                "submission": neutral,
                "kind": item["kind"],
                "id": item["id"],
                "carrier": item.get("carrier") or "",
                "tool": tool["verdict"],
                "tool_rules": " ".join(tool["rules"]),
                "tool_not_run": int(not_run(principle, neutral)),
            }
            for run, verdicts in runs.items():
                row[f"judge {run}"] = int(verdicts[f"{principle}/{neutral}"]["violates"])
            rows.append(row)
            who = [decider for decider in deciders if flagged[neutral][decider]]
            if item["kind"] == "solution" and who:
                reasons = [
                    f"{run}: {_cell(runs[run][f'{principle}/{neutral}'].get('reason') or '')}"
                    for run in runs
                    if runs[run][f"{principle}/{neutral}"]["violates"]
                ]
                rules = ", ".join(f"`{rule}`" for rule in tool["rules"]) or "-"
                candidates.append(
                    f"| `{principle}` | {item['id']} ({neutral}) | {', '.join(who)} | "
                    f"{tool['verdict']}: {rules} | {'; '.join(reasons) or '-'} |"
                )
    lines += [
        "## Řešení, která někdo označil (kandidáti přirozených porušení k ruční kontrole)",
        "",
    ]
    if candidates:
        lines += ["| Princip | Řešení | Označili | Nástroj | Důvody soudců |",
                  "|---|---|---|---|---|", *candidates]
    else:
        lines.append("Žádné.")
    (base / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (base / "results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["principle"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {base / 'results.md'} and {base / 'results.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
