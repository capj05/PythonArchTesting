"""Check every principle of the catalogue against its own variants.

For each ``<principle>/principle.toml`` this runs the tool once over
``<principle>/assignments`` (``--dynamic --sandbox bwrap``) and compares each
variant with what the catalogue entry promises:

- a ``[[neutral]]`` variant must pass: the change is unrelated to the principle;
- an ``[[errors]]`` variant with ``detected_by`` must fail on that marker;
- an ``[[errors]]`` variant with ``gap`` is a known miss and is expected to pass.

For every detected error the student explanation is composed from the entry's
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

from explain import explanation, first_failure, load_entry, run_catalogue

HERE = Path(__file__).resolve().parent


def check_principle(principle_dir: Path) -> tuple[list[str], bool]:
    entry = load_entry(principle_dir)
    results = run_catalogue(principle_dir)
    lines = [f"## {entry['name']} (`{entry['id']}`)", ""]
    lines += ["| Varianta | Druh | Očekáváno | Nástroj | Shoda |", "|---|---|---|---|---|"]
    explanations: list[str] = []
    ok = True
    listed: set[str] = set()

    for item in entry.get("neutral", []):
        listed.add(item["example"])
        verdict = "FAIL" if first_failure(results[item["example"]], None) else "PASS"
        match = verdict == "PASS"
        ok &= match
        lines.append(f"| `{item['example']}` | rušivá změna: {item['title']} | PASS | {verdict} | {'✓' if match else '✗'} |")

    for error in entry.get("errors", []):
        listed.add(error["example"])
        variant_results = results[error["example"]]
        if "gap" in error:
            failure = first_failure(variant_results, None)
            verdict = "FAIL" if failure else "PASS"
            match = verdict == "PASS"
            expected = f"PASS (mezera {error['gap']})"
        else:
            failure = first_failure(variant_results, error["detected_by"])
            verdict = "FAIL" if failure else "PASS"
            match = verdict == "FAIL"
            expected = f"FAIL ({error['detected_by']})"
            if failure:
                explanations += [f"### `{error['example']}`: {error['title']}", "", explanation(error, failure), ""]
        ok &= match
        lines.append(f"| `{error['example']}` | chyba: {error['title']} | {expected} | {verdict} | {'✓' if match else '✗'} |")

    unlisted = sorted(set(results) - listed)
    if unlisted:
        ok = False
        lines += ["", f"Varianty mimo katalog: {', '.join(unlisted)}"]
    lines += ["", "### Vysvětlení pro studenta (složené z katalogu a reportu, bez LLM)", ""]
    lines += explanations
    for gap in entry.get("gaps", []):
        lines += [f"### Mezera {gap['id']}: {gap['title']}", "", " ".join(gap["detail"].split()), ""]
    return lines, ok


def main(argv: list[str]) -> int:
    dirs = [HERE / name for name in argv] or sorted(p.parent for p in HERE.glob("*/principle.toml"))
    output = ["# Ověření katalogu principů", "",
              "Vygenerováno skriptem `verify.py`; neupravovat ručně.", ""]
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
