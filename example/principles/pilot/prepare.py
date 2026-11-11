"""Prepare the blind inputs of the pilot: every submission under a neutral id.

For each principle directory ``<base>/<p>/`` this collects

- the solutions ``solutions/<variant>/<model>-<run>/solution/`` (``variant`` is
  ``text`` or ``skeleton``), and
- the injected variants ``injected/{err,neutral}/<id>-<carrier>/solution/``
  with their ``meta.json`` (``{"kind": "err"|"neutral", "id": ...,
  "carrier": "<variant>/<model>-<run>", "injector": "<model>"}``),

shuffles them together under neutral ids (``w001``...) and writes

- ``whole/wNNN.md``: the complete code of the submission, files in path order
  (what a judge reads);
- ``key.json``: ``wNNN`` -> ``{"path", "kind": "solution"|"err"|"neutral",
  "id", "carrier", "sha256"}`` (never shown to a judge; ``path`` is relative
  to ``<base>/<p>``, ``carrier`` is ``null`` for a solution, ``injector`` is
  added for an injected variant, ``sha256`` is the hash of ``whole/wNNN.md``,
  which ``run_tool.py`` and ``score.py`` check);
- ``batches.json``: the ids in batches of at most ``--batch-size`` (4), each
  batch holding at most one submission of a carrier family (a solution and
  every variant injected into it), so that no judge sees two near-identical
  submissions together. There are as many batches as the submissions need at
  that size, or as the largest family has members, whichever is more.

An injected variant's directory must be named ``<id>-<carrier_>`` (its
``carrier`` with ``/`` as ``_``), and one ``(id, carrier)`` pair may occur
only once. The seed is fixed, so the same inputs give the same ids and
batches.

Usage, from the repository root::

    python example/principles/pilot/prepare.py [--seed 7] [--batch-size 4]
        [--base DIR] [principle ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parent
sys.path.insert(0, str(CATALOGUE))

from explain import load_entry  # noqa: E402  (the shared module lives one level up)

VARIANTS = ("text", "skeleton")
KINDS = ("err", "neutral")
# The neutral defect the catalogue does not list (id -> description, in Czech).
EXTRA_NEUTRAL = {
    "input_handling": (
        "chyba ošetření vstupu: neplatný nebo prázdný vstup se neodmítne nebo"
        " neošetří (chybí kontrola nebo zachycení výjimky)"
    ),
}


def principles(base: Path, names: list[str]) -> list[Path]:
    """The principle directories of the pilot (with solutions) to work on."""
    if names:
        return [base / name for name in names]
    return sorted(path.parent for path in base.glob("*/solutions"))


def files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    }


def whole(neutral: str, code: dict[str, str]) -> str:
    body = "\n".join(
        f"### `{name}`\n\n```python\n{text}{'' if text.endswith(chr(10)) else chr(10)}```\n"
        for name, text in sorted(code.items())
    )
    return f"# Odevzdání {neutral}\n\n{body}"


def sha256(text: str) -> str:
    """The hash of a ``whole/wNNN.md`` text, as stored in ``key.json``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def carrier_dir(carrier: str) -> str:
    """``skeleton/opus-1`` as a directory name part: ``skeleton_opus-1``."""
    return carrier.replace("/", "_")


def collect(principle_dir: Path) -> list[dict[str, Any]]:
    """Every submission of one principle, in a fixed order (before shuffling)."""
    entry = load_entry(CATALOGUE / principle_dir.name)
    known = {
        "err": {error["id"] for error in entry.get("errors", [])},
        "neutral": {item["id"] for item in entry.get("neutral", [])} | set(EXTRA_NEUTRAL),
    }
    items: list[dict[str, Any]] = []
    carriers: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for variant_dir in sorted((principle_dir / "solutions").glob("*")):
        if variant_dir.name not in VARIANTS:
            raise SystemExit(f"{variant_dir}: the variant must be one of {VARIANTS}")
        for run_dir in sorted(variant_dir.iterdir()):
            if not (run_dir / "solution" / "__init__.py").is_file():
                raise SystemExit(f"{run_dir}/solution is not a package")
            label = f"{variant_dir.name}/{run_dir.name}"
            carriers.add(label)
            items.append({"path": (run_dir / "solution").relative_to(principle_dir).as_posix(),
                          "kind": "solution", "id": label, "carrier": None})
    for kind in KINDS:
        for variant_dir in sorted((principle_dir / "injected" / kind).glob("*")):
            meta = json.loads((variant_dir / "meta.json").read_text(encoding="utf-8"))
            problems = []
            if meta.get("kind") != kind:
                problems.append(f"kind {meta.get('kind')!r} is not {kind!r}")
            if meta.get("id") not in known[kind]:
                problems.append(f"id {meta.get('id')!r} is not one of {sorted(known[kind])}")
            if meta.get("carrier") not in carriers:
                problems.append(f"carrier {meta.get('carrier')!r} is not a solution")
            if not (variant_dir / "solution" / "__init__.py").is_file():
                problems.append("solution/ is not a package")
            if isinstance(meta.get("id"), str) and isinstance(meta.get("carrier"), str):
                expected = f"{meta['id']}-{carrier_dir(meta['carrier'])}"
                if variant_dir.name != expected:
                    problems.append(f"the directory must be named {expected!r}")
                pair = (meta["id"], meta["carrier"])
                if pair in pairs:
                    problems.append(f"{pair} is injected twice")
                pairs.add(pair)
            if problems:
                raise SystemExit(f"{variant_dir}: " + "; ".join(problems))
            items.append({"path": (variant_dir / "solution").relative_to(principle_dir).as_posix(),
                          "kind": kind, "id": meta["id"], "carrier": meta["carrier"],
                          "injector": meta.get("injector")})
    return items


def family(item: dict[str, Any]) -> str:
    """The carrier family of a submission: its carrier, or itself for a solution."""
    return str(item["carrier"] or item["id"])


def batch(ids: list[str], families: dict[str, str], size: int, rng: random.Random) -> list[list[str]]:
    """Ids in batches of at most ``size``, at most one per family in a batch.

    Families go largest first (ties in a seeded random order); each member
    goes to the least filled batch that has no member of its family yet (ties
    to the lowest batch). Raises ``SystemExit`` when that is impossible.
    """
    if size < 1:
        raise SystemExit(f"the batch size must be at least 1, not {size}")
    members: dict[str, list[str]] = {}
    for neutral in ids:
        members.setdefault(families[neutral], []).append(neutral)
    largest = max((len(group) for group in members.values()), default=0)
    count = max(-(-len(ids) // size), largest)
    order = sorted(members)
    rng.shuffle(order)
    order.sort(key=lambda name: -len(members[name]))
    batches: list[list[str]] = [[] for _ in range(count)]
    for name in order:
        for neutral in members[name]:
            free = [i for i, group in enumerate(batches)
                    if len(group) < size and all(families[n] != name for n in group)]
            if not free:
                raise SystemExit(f"cannot batch family {name!r} by {size} with one member per batch")
            batches[min(free, key=lambda i: (len(batches[i]), i))].append(neutral)
    for group in batches:
        names = [families[n] for n in group]
        if len(group) > size or len(names) != len(set(names)):
            raise SystemExit(f"batch {sorted(group)} breaks the one-per-family rule")
    return [sorted(group) for group in batches if group]


def prepare(principle_dir: Path, seed: int, batch_size: int) -> tuple[int, int]:
    items = collect(principle_dir)
    rng = random.Random(f"{seed}-{principle_dir.name}")
    rng.shuffle(items)
    out = principle_dir / "whole"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    key: dict[str, Any] = {}
    for index, item in enumerate(items, start=1):
        neutral = f"w{index:03d}"
        text = whole(neutral, files(principle_dir / item["path"]))
        (out / f"{neutral}.md").write_text(text, encoding="utf-8")
        key[neutral] = {**item, "sha256": sha256(text)}
    ids = list(key)
    batches = batch(ids, {n: family(key[n]) for n in ids}, batch_size, rng)
    (principle_dir / "key.json").write_text(
        json.dumps(key, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (principle_dir / "batches.json").write_text(json.dumps(batches, indent=1) + "\n", encoding="utf-8")
    return len(ids), len(batches)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--base", type=Path, default=HERE, help="the pilot directory")
    parser.add_argument("principle", nargs="*")
    args = parser.parse_args(argv)
    dirs = principles(args.base, args.principle)
    if not dirs:
        raise SystemExit(f"no <principle>/solutions/ under {args.base}")
    for principle_dir in dirs:
        count, batches = prepare(principle_dir, args.seed, args.batch_size)
        print(f"{principle_dir.name}: {count} submissions in {batches} batches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
