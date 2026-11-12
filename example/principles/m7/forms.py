"""Generate and read the owner's two M7 forms: ``review.md`` and ``owner_vo5.md``.

- ``forms.py review`` writes ``review.md``, the owner's ground truth on a
  sample of the solutions: every solution that any decider flags (the tool,
  computed now with the current tool, or any judge run of ``--judges``),
  every one on which they do not all agree (or the tool gives no verdict),
  and ``--drawn`` (6) of the rest **per stage** (``harness.STAGES``), drawn
  with the seed ``harness.REVIEW_SEED`` from the stage's principles, so that
  stage 1's draw stays the same when stage 2's solutions are added, and
  stage 2 gets a random check of its own; ``--all`` puts every solution in
  the form. The form
  is blind: per solution only its path, the assignment's path and the fields
  ``violates:`` (``yes`` / ``no``) and ``note:``. Every judge run must have
  judged every solution (else exit 1).
- ``forms.py vo5`` writes ``owner_vo5.md``: the explanations M6 selected for
  the owner (``../m6/results-vo3-vo5.md``, the list under "For the owner's
  review", ``--items`` of them), each with the path of the code, the
  principle, the explanation itself, and the fields ``location:``,
  ``principle:``, ``reason:`` (0-2, M6's rubric for the rater, printed in the
  form) and ``note:``. The rater's (Opus's) scores are not in the form.

The first line of each form is an HTML comment holding, base64-encoded JSON,
what was generated: the item set and, for ``review.md``, the tool's verdict
at generation time and why each solution is in the sample (so a reader of
the raw file does not see them). Neither form is overwritten without
``--force`` (it may hold the owner's answers). ``score.py`` reads both with
``read_review`` and ``read_vo5``, strictly: the items must be exactly the
generated ones, each heading once, each field on exactly one line, and a
non-empty line that is not a field (an answer under an empty ``violates:``)
is an error, as is a value out of range; an empty field is "pending owner
review".

Usage, from the repository root::

    python example/principles/m7/forms.py review [--all]
    python example/principles/m7/forms.py vo5
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402

REVIEW = "review.md"
VO5 = "owner_vo5.md"
M6_RESULTS = "results-vo3-vo5.md"
_ITEM = re.compile(r"^## \d+\. `([^`]+)`[ \t]*$", re.M)
_YES = {"yes": True, "y": True, "ano": True, "no": False, "n": False, "ne": False}


_HEADER = re.compile(
    r"^<!-- m7-form (\w+), do not edit this line: ([A-Za-z0-9+/=]+) -->$", re.M
)


class FormError(Exception):
    """A form that does not parse; the message names the item."""


def _header(kind: str, payload: dict[str, Any]) -> str:
    """The hidden first line of a form: what was generated (the item set and,
    for ``review``, what ``score.py`` compares with later), as base64 JSON
    so that reading the raw form does not show the deciders' verdicts."""
    data = base64.b64encode(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    return f"<!-- m7-form {kind}, do not edit this line: {data} -->"


def _payload(path: Path, text: str, kind: str) -> dict[str, Any]:
    found = _HEADER.findall(text)
    if len(found) != 1 or found[0][0] != kind:
        raise FormError(
            f"{path}: not one header line `<!-- m7-form {kind}, ... -->`; regenerate"
            " the form (forms.py, --force) and copy the answers over"
        )
    try:
        payload = json.loads(base64.b64decode(found[0][1], validate=True))
    except (ValueError, binascii.Error) as error:
        raise FormError(f"{path}: the header line is damaged ({error})") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise FormError(f"{path}: the header line holds no item set")
    return payload


def _blocks(path: Path, text: str, expected: list[str]) -> dict[str, str]:
    """``name`` -> the text under its heading; the headings must be the
    ``expected`` items, each exactly once."""
    marks = list(_ITEM.finditer(text))
    names = [mark.group(1) for mark in marks]
    twice = sorted({name for name in names if names.count(name) > 1})
    if twice:
        raise FormError(
            f"{path}: the item {', '.join(map(repr, twice))} has two headings"
        )
    missing = [name for name in expected if name not in names]
    extra = [name for name in names if name not in expected]
    if missing or extra:
        raise FormError(
            f"{path}: the items are not the ones generated:"
            + (f" missing {missing}" if missing else "")
            + (f" not generated {extra}" if extra else "")
        )
    return {
        mark.group(1): text[
            mark.end() : (
                marks[index + 1].start() if index + 1 < len(marks) else len(text)
            )
        ]
        for index, mark in enumerate(marks)
    }


def _fields(path: Path, name: str, block: str, keys: tuple[str, ...]) -> dict[str, str]:
    """``key`` -> its value in one item's block. Each of ``keys`` and
    ``note`` is on exactly one line ``key: value``; from the first of them
    on, every non-empty line is a field, except lines after ``note:`` (the
    note goes on). A line that is not a field before ``note:`` (an answer
    written under an empty ``violates:``) is an error."""
    names = (*keys, "note")
    lines = block.splitlines()
    seen: dict[str, str] = {}
    started = in_note = False
    for number, line in enumerate(lines, start=1):
        field = re.match(rf"^({'|'.join(names)}):[ \t]*(.*?)[ \t]*$", line)
        if field:
            key = field.group(1)
            if key in seen:
                raise FormError(f"{path}: `{name}` has more than one `{key}:` line")
            seen[key] = field.group(2)
            started, in_note = True, key == "note"
            continue
        if not started or not line.strip():
            continue
        if in_note:
            seen["note"] = f"{seen['note']} {line.strip()}".strip()
            continue
        raise FormError(
            f"{path}: `{name}`: the line {line.strip()!r} is not a field; write the"
            " answer on the same line as its field, e.g. `violates: yes`"
        )
    absent = [key for key in names if key not in seen]
    if absent:
        raise FormError(f"{path}: `{name}` has no `{absent[0]}:` line")
    return seen


def _link(path: Path, start: Path) -> str:
    """A Markdown link to ``path``, relative to the form's directory ``start``."""
    target = Path(os.path.relpath(path.resolve(), start.resolve())).as_posix()
    return f"[{path.name}]({target.replace(' ', '%20')})"


def _file_links(directory: Path, start: Path) -> list[str]:
    """One indented list line with a link per source file under ``directory``."""
    files = sorted(
        p
        for p in directory.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.suffix in (".py", ".md", ".txt", ".toml")
    )
    return [f"  - {_link(p, start)}" for p in files]


def disagree(tool: str, judges: dict[str, bool]) -> bool:
    """Whether the tool and the judges do not all say the same (a tool
    without a verdict always counts as a disagreement)."""
    if tool not in (harness.TOOL_VIOLATES, harness.TOOL_PASSES):
        return True
    return any(
        violates != (tool == harness.TOOL_VIOLATES) for violates in judges.values()
    )


def flagged(tool: str, judges: dict[str, bool]) -> bool:
    """Whether any decider (the tool or a judge run) says the solution
    violates the principle."""
    return tool == harness.TOOL_VIOLATES or any(judges.values())


def must_review(tool: str, judges: dict[str, bool]) -> bool:
    """Whether a solution enters the sample by itself: flagged by any
    decider, or the deciders disagree (or the tool gives no verdict)."""
    return flagged(tool, judges) or disagree(tool, judges)


def decisions(
    base: Path, judges: tuple[str, ...]
) -> dict[str, tuple[dict[str, Any], dict[str, bool]]]:
    """``<p>/<student>`` -> (the tool's verdict now, run -> violates) for every
    collected solution; exits when a judgment is missing."""
    found: dict[str, tuple[dict[str, Any], dict[str, bool]]] = {}
    problems: list[str] = []
    for principle in harness.principles():
        names = harness.students(base, principle)
        if not names:
            continue
        judged = harness.judgments(base, principle, judges, problems)
        if problems:
            continue
        tool = harness.tool_verdicts(base, principle)
        for name in names:
            found[f"{principle}/{name}"] = (
                tool[name],
                {run: judged[run][name] for run in judges},
            )
    if problems:
        raise SystemExit("\n".join(problems))
    if not found:
        raise SystemExit(f"{base / 'results' / 'code'}: no solution collected")
    return found


def sample(
    found: dict[str, tuple[dict[str, Any], dict[str, bool]]],
    drawn: int,
    everything: bool,
) -> dict[str, str]:
    """``<p>/<student>`` -> why it is in the sample: ``flagged`` (by any
    decider), ``disagreement`` (no one flags, the tool gives no verdict),
    ``drawn`` (``drawn`` of the rest of each stage, seed
    ``harness.REVIEW_SEED``) or, with ``everything``, ``all``. Each stage
    draws from its own rest, sorted and shuffled alone, so a stage's draw does
    not depend on the solutions of another stage."""
    why: dict[str, str] = {}
    for name, (tool, ruled) in found.items():
        if flagged(tool["verdict"], ruled):
            why[name] = "flagged"
        elif disagree(tool["verdict"], ruled):
            why[name] = "disagreement"
    stages = sorted({harness.stage_of(name.split("/", 1)[0]) for name in found})
    for stage in stages:
        rest = sorted(
            name
            for name in found
            if name not in why and harness.stage_of(name.split("/", 1)[0]) == stage
        )
        random.Random(harness.REVIEW_SEED).shuffle(rest)
        for name in rest[:drawn]:
            why[name] = "drawn"
    if everything:
        for name in found:
            why.setdefault(name, "all")
    return {name: why[name] for name in sorted(why)}


def review(
    base: Path,
    pilot: Path,
    judges: tuple[str, ...],
    drawn: int,
    everything: bool = False,
) -> str:
    """The text of ``review.md``: blind, it shows no decider's verdict."""
    found = decisions(base, judges)
    chosen = sample(found, drawn, everything)
    count = {
        kind: sum(1 for why in chosen.values() if why == kind)
        for kind in ("flagged", "disagreement", "drawn", "all")
    }
    rest = len(found) - count["flagged"] - count["disagreement"]
    if everything:
        which = f"all {len(found)} solutions."
    else:
        which = (
            f"{len(chosen)} of the {len(found)} solutions: every one that the tool or a"
            " judge run flags or on which they disagree"
            f" ({count['flagged'] + count['disagreement']}), and {count['drawn']} drawn"
            f" from the other {rest} ({drawn} per stage, seed {harness.REVIEW_SEED})."
        )
    payload = {
        "items": list(chosen),
        "judges": list(judges),
        "tool": {name: found[name][0]["verdict"] for name in chosen},
        "why": chosen,
    }
    lines = [
        _header("review", payload),
        "# M7: the owner's ground truth on a sample of the solutions",
        "",
        "Generated by `forms.py review`; fill in the fields, do not change anything else"
        " (the first line, an HTML comment, is what `score.py` checks the form against)."
        " Per solution: read its code (every file under the path) and the principle's"
        " section of the assignment, and decide whether the code violates the principle"
        " **as the assignment states it**; any other fault of the code does not count."
        " Write `yes` or `no` on the `violates:` line itself; `note:` is optional. A"
        " solution left empty is reported as `pending owner review`. The form is blind:"
        " it shows neither the tool's nor the judges' verdicts, nor why a solution is in"
        " the sample.",
        "",
        f"The sample: {which}",
        "",
    ]
    for index, name in enumerate(chosen, start=1):
        principle, student = name.split("/", 1)
        lines += [
            f"## {index}. `{name}`",
            "",
            f"- solution: `{harness.shown(harness.code_dir(base, principle) / student)}/`",
            *_file_links(harness.code_dir(base, principle) / student, base),
            f"- assignment: {_link(harness.assignment(pilot, principle), base)}",
            "",
            "violates:",
            "note:",
            "",
        ]
    return "\n".join(lines)


def read_review(path: Path, problems: list[str]) -> dict[str, dict[str, Any]]:
    """``<p>/<student>`` -> ``{"violates": True|False|None, "note", "tool",
    "why"}`` from ``review.md`` (``None``: not answered yet; ``tool``: the
    tool's verdict when the form was generated); an absent form is an empty
    sample. A form that does not parse, or a value other than yes/no, goes
    to ``problems``."""
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        payload = _payload(path, text, "review")
        blocks = _blocks(path, text, payload["items"])
        found: dict[str, dict[str, Any]] = {}
        for name, block in blocks.items():
            fields = _fields(path, name, block, ("violates",))
            value = fields["violates"]
            if value and value.lower() not in _YES:
                raise FormError(
                    f"{path}: `{name}`: violates is {value!r}, not yes or no"
                )
            found[name] = {
                "violates": _YES[value.lower()] if value else None,
                "note": fields["note"],
                "tool": payload.get("tool", {}).get(name, ""),
                "why": payload.get("why", {}).get(name, ""),
            }
    except FormError as error:
        problems.append(str(error))
        return {}
    return found


def vo5_items(m6_base: Path, wanted: int) -> list[str]:
    """``<p>/<submission>`` of the explanations M6 selected for the owner."""
    path = m6_base / M6_RESULTS
    if not path.is_file():
        raise SystemExit(f"{path} is missing: run ../m6/score.py first")
    text = path.read_text(encoding="utf-8")
    _, marker, listing = text.partition("For the owner's review")
    items = re.findall(r"^- `([^`/]+/[^`]+)`:", listing.split("\n## ", 1)[0], re.M)
    if not marker or len(items) != wanted:
        raise SystemExit(
            f"{path}: {len(items)} explanations listed for the owner's review, not {wanted}"
        )
    return items


def vo5(m6_base: Path, pilot: Path, wanted: int, at: Path | None = None) -> str:
    """The text of ``owner_vo5.md``."""
    from pythonarchtesting.mcp_server import principles

    items = vo5_items(m6_base, wanted)
    lines = [
        _header("vo5", {"items": items}),
        "# M6 VO5: the owner's rating of the explanations",
        "",
        "Generated by `forms.py vo5`; fill in the fields, do not change anything else"
        " (the first line, an HTML comment, is what `score.py` checks the form against)."
        f" These are the {wanted} explanations of the tool's findings that M6 selected for"
        f" the owner (`{harness.shown(m6_base / M6_RESULTS)}`). Rate each by the rubric"
        " below, the one the M6 rater used, with 0, 1 or 2 after `location:`,"
        " `principle:` and `reason:`, on the line of the field itself; `note:` is"
        " optional. In the rubric, `code/`,"
        " `explanation.md` and `principle.json` are the paths and the principle given"
        " with each explanation. An explanation not rated in all three is reported as"
        " `pending owner review`.",
        "",
        *(
            "#" + line if line.startswith("#") else line
            for line in harness.m6_stage.RUBRIC.splitlines()
        ),
        "",
    ]
    for index, name in enumerate(items, start=1):
        principle, submission = name.split("/", 1)
        explanation = (
            m6_base / "results" / "explanations" / principle / f"{submission}.md"
        )
        rating = m6_base / "results" / "ratings" / principle / f"{submission}.json"
        for path in (explanation, rating):
            if not path.is_file():
                raise SystemExit(f"{path} is missing")
        try:
            code = harness.m6.submission(m6_base, pilot, principle, submission)
        except SystemExit as error:
            raise SystemExit(
                f"{error}; the code of the M6 explanations is the pilot's unversioned"
                f" injected/ data, needed under {pilot} (--pilot)"
            ) from error
        entry = principles.describe_principle(principle)
        text = explanation.read_text(encoding="utf-8").strip()
        lines += [
            f"## {index}. `{name}`",
            "",
            f"- code: `{harness.shown(code)}/`",
            *_file_links(code, at or Path(__file__).resolve().parent),
            f"- explanation: {_link(explanation, at or Path(__file__).resolve().parent)}",
            f"- the principle: {entry['name']}: {' '.join(entry['summary'].split())}",
            "",
            *(f"> {line}".rstrip() for line in text.splitlines()),
            "",
            "location:",
            "principle:",
            "reason:",
            "note:",
            "",
        ]
    return "\n".join(lines)


def read_vo5(path: Path, problems: list[str]) -> dict[str, dict[str, Any]]:
    """``<p>/<submission>`` -> ``{"location", "principle", "reason": 0-2 or
    None, "note"}`` from ``owner_vo5.md``; an absent form is no answer. A
    form that does not parse, or a value out of range, goes to ``problems``."""
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    keys = tuple(harness.m6.RATING_KEYS)
    found: dict[str, dict[str, Any]] = {}
    try:
        payload = _payload(path, text, "vo5")
        for name, block in _blocks(path, text, payload["items"]).items():
            fields = _fields(path, name, block, keys)
            scores: dict[str, Any] = {"note": fields["note"]}
            for key in keys:
                value = fields[key]
                if value and value not in ("0", "1", "2"):
                    raise FormError(
                        f"{path}: `{name}`: {key} is {value!r}, not 0, 1 or 2"
                    )
                scores[key] = int(value) if value else None
            found[name] = scores
    except FormError as error:
        problems.append(str(error))
        return {}
    return found


def _write(path: Path, text: str, force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(
            f"{path} exists (it may hold the owner's answers); pass --force"
        )
    path.write_text(text, encoding="utf-8")
    print(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="form", required=True)
    for form in ("review", "vo5"):
        sub = commands.add_parser(form)
        sub.add_argument("--base", type=Path, default=HERE, help="the M7 directory")
        sub.add_argument(
            "--pilot", type=Path, default=harness.PILOT, help="the pilot directory"
        )
        sub.add_argument(
            "--force", action="store_true", help="replace an existing form"
        )
        if form == "review":
            sub.add_argument("--judges", default=",".join(harness.JUDGE_RUNS))
            sub.add_argument(
                "--drawn",
                type=int,
                default=6,
                help="how many of the solutions no decider flags and all agree on,"
                " per stage",
            )
            sub.add_argument(
                "--all", action="store_true", help="put every solution in the form"
            )
        else:
            sub.add_argument(
                "--m6", type=Path, default=harness.M6, help="the M6 directory"
            )
            sub.add_argument("--items", type=int, default=6)
    args = parser.parse_args(argv)
    base, pilot = args.base.resolve(), args.pilot.resolve()
    if args.form == "review":
        judges = tuple(run for run in args.judges.split(",") if run)
        text = review(base, pilot, judges, args.drawn, args.all)
        _write(base / REVIEW, text, args.force)
    else:
        _write(base / VO5, vo5(args.m6.resolve(), pilot, args.items, base), args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
