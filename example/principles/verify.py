"""Check every principle of the catalogue against its own variants.

For each ``<principle>/principle.toml`` (a pointer to the packaged catalogue
entry, ``pythonarchtesting.principles``, with the example variant of each of
its items) this runs the tool once over ``<principle>/assignments``
(``--dynamic --sandbox bwrap``) and compares each variant with what the
catalogue entry promises:

- a neutral change's variant must pass: the change is unrelated to the principle;
- an error's variant with ``detected_by`` must fail on that marker, and the first
  fact of the failure must match the error's declared ``signature`` on every key
  it declares, and ``choose_error`` must pick that error for the failure;
- an error's variant with ``gap`` is a known miss and is expected to pass.

The last column lists every error the tool classifies the variant's findings
as (``classify_target``, which takes the read a write makes for the write),
in the order found: one defect should give one error.

For every detected error the explanation is composed from the entry's
``what`` / ``why`` / ``fix`` and the facts of the report, without any LLM; the
placeholders are listed in ``explain.py``, which ``pilot/run_tool.py`` shares.
Writes ``results.md`` next to this file; exits 1 when a variant does not behave
as promised or a variant directory is missing from the catalogue.

Usage: python example/principles/verify.py [principle ...]
Needs Python 3.11+ (tomllib); the tool itself supports 3.10.
"""

from __future__ import annotations

import sys
from pathlib import Path

from explain import choose_error, explanation, first_failure, load_entry, run_catalogue, signature

from pythonarchtesting.principles import classify_target, get_principle, signature_matches

HERE = Path(__file__).resolve().parent


def all_findings(principle_id: str, results: list[dict]) -> str:
    """The distinct errors of a variant's findings, in the order found."""
    found = classify_target(get_principle(principle_id), results)
    ids = dict.fromkeys(
        f"`{f.error_id}`" if f.error_id else ("not judged" if f.not_judged else "unclassified")
        for f in found
    )
    return ", ".join(ids) or "—"


def check_principle(principle_dir: Path) -> tuple[list[str], bool]:
    entry = load_entry(principle_dir)
    results = run_catalogue(principle_dir)
    lines = [f"## {entry['name']} (`{entry['id']}`)", ""]
    lines += [
        "| Variant | Kind | Expected | Tool | Match | All findings |",
        "|---|---|---|---|---|---|",
    ]
    explanations: list[str] = []
    ok = True
    listed: set[str] = set()

    for item in entry.get("neutral", []):
        listed.add(item["example"])
        verdict = "FAIL" if first_failure(results[item["example"]], None) else "PASS"
        match = verdict == "PASS"
        ok &= match
        found = all_findings(entry["id"], results[item["example"]])
        lines.append(f"| `{item['example']}` | neutral change: {item['title']} | PASS | {verdict} | {'✓' if match else '✗'} | {found} |")

    for error in entry.get("errors", []):
        listed.add(error["example"])
        variant_results = results[error["example"]]
        if "gap" in error:
            failure = first_failure(variant_results, None)
            verdict = "FAIL" if failure else "PASS"
            match = verdict == "PASS"
            expected = f"PASS (gap {error['gap']})"
        else:
            failure = first_failure(variant_results, error["detected_by"])
            verdict = "FAIL" if failure else "PASS"
            match = verdict == "FAIL"
            expected = f"FAIL ({error['detected_by']})"
            if failure and not signature_matches(error["signature"], signature(failure)):
                match = False
                verdict = f"FAIL, signature {signature(failure)} is not the declared one"
            elif failure and (chosen := choose_error(entry, failure)) is not error:
                match = False
                verdict = f"FAIL, classified as {chosen['id'] if chosen else 'no error'}"
            if failure:
                explanations += [f"### `{error['example']}`: {error['title']}", "", explanation(error, failure), ""]
        ok &= match
        found = all_findings(entry["id"], variant_results)
        lines.append(f"| `{error['example']}` | error: {error['title']} | {expected} | {verdict} | {'✓' if match else '✗'} | {found} |")

    unlisted = sorted(set(results) - listed)
    if unlisted:
        ok = False
        lines += ["", f"Variants outside the catalogue: {', '.join(unlisted)}"]
    lines += ["", "### Explanations (composed from the catalogue and the report, no LLM)", ""]
    lines += explanations
    for gap in entry.get("gaps", []):
        lines += [f"### Gap {gap['id']}: {gap['title']}", "", gap["detail"], ""]
    return lines, ok


def main(argv: list[str]) -> int:
    dirs = [HERE / name for name in argv] or sorted(p.parent for p in HERE.glob("*/principle.toml"))
    output = ["# Verification of the principle catalogue", "",
              "Generated by `verify.py`; do not edit by hand.", ""]
    all_ok = True
    for principle_dir in dirs:
        lines, ok = check_principle(principle_dir)
        output += lines
        all_ok &= ok
        print(f"{principle_dir.name}: {'OK' if ok else 'MISMATCH'}")
    (HERE / "results.md").write_text("\n".join(output) + "\n", encoding="utf-8")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
