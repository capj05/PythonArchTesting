"""Prepare the LLM-as-judge experiment (E3): blind inputs for a judge.

For both programs of the architectural-mutant evaluation, every variant (the
hand-written mutants and equivalents of ``mutants.py`` and the held-out ones
of ``llm_mutants.py``) is applied to a copy of ``solution/`` and turned into a
unified diff. The judge sees, per program, ``context.md`` (the intended
architecture in prose and the solution's code) and the diffs under neutral
ids (``v001``...), shuffled into batches that mix mutants and equivalents.
Which id is which variant is in ``key.json``, which the judge must not read.

``--whole`` prepares the whole-submission run instead: each variant as the
complete code of the submission (every file, not a diff), so the judge must
find what is wrong itself, plus the 24 independently written solutions of E2
(``example/llm_solutions/generated``), all under new neutral ids
(``<program>/whole/wNNN.md``, ``batches-whole.json``, ``key-whole.json``).

Usage, from the repository root::

    python example/llm_judge/prepare.py [--batch-size 10] [--seed 7]
    python example/llm_judge/prepare.py --whole [--batch-size 8]
"""

from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import random
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent
PROGRAMS = {
    "program1": EXAMPLES / "architectural_mutants",
    "program2": EXAMPLES / "architectural_mutants_2",
}
# Whole submissions also cover the larger program 3 (T5); its diffs are not
# judged.
WHOLE_PROGRAMS = {
    **PROGRAMS,
    "program3": EXAMPLES / "architectural_mutants_3",
}
# The intended architecture, as the assignment states it to students.
ASSIGNMENTS = {
    "program1": EXAMPLES / "llm_solutions" / "program1" / "assignment.md",
    "program2": EXAMPLES / "llm_solutions" / "program2" / "assignment.md",
    "program3": EXAMPLES / "llm_solutions" / "program3" / "assignment.md",
}


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    }


def _diff(before: dict[str, str], after: dict[str, str]) -> str:
    chunks = []
    for name in sorted(set(before) | set(after)):
        old, new = before.get(name, ""), after.get(name, "")
        if old == new:
            continue
        chunks.extend(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{name}" if name in before else "/dev/null",
                tofile=f"b/{name}" if name in after else "/dev/null",
            )
        )
    return "".join(chunks)


def _whole(files: dict[str, str]) -> str:
    return "\n".join(
        f"### `{name}`\n\n```python\n{text}```\n"
        for name, text in sorted(files.items())
    )


def _solutions(name: str) -> list[tuple[str, Path]]:
    """E2's generated solutions of one program: (``variant/run``, directory)."""
    base = EXAMPLES / "llm_solutions" / "generated" / name
    if not base.is_dir():
        raise SystemExit(f"{base} is missing; generate E2 first")
    return [
        (f"{variant.name}/{run.name}", run / "solution")
        for variant in sorted(base.iterdir())
        for run in sorted(variant.iterdir())
        if (run / "solution").is_dir()
    ]


def _prepare_whole(args: argparse.Namespace, run: Any) -> int:
    wanted = set(args.only.split(",")) if args.only else set(WHOLE_PROGRAMS)
    key_path = HERE / "key-whole.json"
    # Programs not prepared now keep their keys (and their judges' verdicts).
    key: dict[str, Any] = {
        neutral: item
        for neutral, item in (
            json.loads(key_path.read_text(encoding="utf-8"))
            if key_path.is_file()
            else {}
        ).items()
        if item["program"] not in wanted
    }
    for name, program in WHOLE_PROGRAMS.items():
        if name not in wanted:
            continue
        out = HERE / name
        whole = out / "whole"
        if whole.exists():
            shutil.rmtree(whole)
        whole.mkdir(parents=True)
        if not (out / "context.md").is_file():
            (out / "context.md").write_text(_context(name, program), encoding="utf-8")
        items: list[tuple[dict[str, Any], dict[str, str]]] = []
        for source in ("mutants.py", "llm_mutants.py"):
            module = _load(program / source, f"_{name}_{source[:-3]}_whole")
            for variant in [*module.MUTANTS, *module.EQUIVALENTS]:
                with tempfile.TemporaryDirectory() as tmp:
                    target = Path(tmp) / run.PACKAGE
                    shutil.copytree(program / "solution", target)
                    run._apply(variant, target)
                    files = _files(target)
                items.append(
                    (
                        {
                            "program": name,
                            "set": "held-out" if source == "llm_mutants.py" else "hand",
                            "id": variant["id"],
                            "kind": (
                                "equivalent"
                                if variant["id"].startswith("E")
                                else "mutant"
                            ),
                            "operator": variant.get("operator", "-"),
                            "description": variant["description"],
                        },
                        files,
                    )
                )
        for label, path in _solutions(name):
            items.append(
                (
                    {
                        "program": name,
                        "set": "E2 " + label.split("/")[0],
                        "id": label,
                        "kind": "solution",
                        "operator": "-",
                        "description": "independently written solution (E2)",
                    },
                    _files(path),
                )
            )
        rng = random.Random(f"{args.seed}-{name}-whole")
        rng.shuffle(items)
        ids = []
        for index, (item, files) in enumerate(items, start=1):
            neutral = f"w{index:03d}"
            (whole / f"{neutral}.md").write_text(
                f"# Submission {neutral}\n\n{_whole(files)}", encoding="utf-8"
            )
            key[f"{name}/{neutral}"] = item
            ids.append(neutral)
        batches = [
            ids[i : i + args.batch_size] for i in range(0, len(ids), args.batch_size)
        ]
        (out / "batches-whole.json").write_text(
            json.dumps(batches, indent=1), encoding="utf-8"
        )
        print(f"{name}: {len(ids)} whole submissions in {len(batches)} batches")
    key_path.write_text(
        json.dumps(dict(sorted(key.items())), indent=1), encoding="utf-8"
    )
    return 0


def _context(name: str, program: Path) -> str:
    assignment = ASSIGNMENTS[name].read_text(encoding="utf-8")
    code = "\n".join(
        f"### `{file}`\n\n```python\n{text}```\n"
        for file, text in _files(program / "solution").items()
    )
    return (
        f"# {name}: intended architecture and the correct solution\n\n"
        "## The assignment (the architecture section is what is graded)\n\n"
        f"{assignment}\n\n## The correct solution\n\n{code}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--whole", action="store_true", help="whole submissions instead of diffs"
    )
    parser.add_argument(
        "--only",
        help="comma-separated programs to prepare (whole submissions); the "
        "others keep their keys",
    )
    args = parser.parse_args()
    sys.path.insert(0, str(EXAMPLES / "architectural_mutants"))
    run = _load(EXAMPLES / "architectural_mutants" / "run.py", "_harness_run")
    if args.whole:
        return _prepare_whole(args, run)
    key: dict[str, Any] = {}
    for name, program in PROGRAMS.items():
        out = HERE / name
        if out.exists():
            shutil.rmtree(out)
        (out / "variants").mkdir(parents=True)
        (out / "context.md").write_text(_context(name, program), encoding="utf-8")
        variants = []
        for source in ("mutants.py", "llm_mutants.py"):
            module = _load(program / source, f"_{name}_{source[:-3]}")
            for variant in [*module.MUTANTS, *module.EQUIVALENTS]:
                variants.append((source, variant))
        before = _files(program / "solution")
        ids = []
        rng = random.Random(f"{args.seed}-{name}")
        rng.shuffle(variants)
        for index, (source, variant) in enumerate(variants, start=1):
            neutral = f"v{index:03d}"
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / run.PACKAGE
                shutil.copytree(program / "solution", target)
                run._apply(variant, target)
                after = _files(target)
            (out / "variants" / f"{neutral}.diff").write_text(
                _diff(before, after), encoding="utf-8"
            )
            key[f"{name}/{neutral}"] = {
                "program": name,
                "set": "held-out" if source == "llm_mutants.py" else "hand",
                "id": variant["id"],
                "kind": "equivalent" if variant["id"].startswith("E") else "mutant",
                "operator": variant.get("operator", "-"),
                "description": variant["description"],
            }
            ids.append(neutral)
        batches = [
            ids[i : i + args.batch_size] for i in range(0, len(ids), args.batch_size)
        ]
        (out / "batches.json").write_text(
            json.dumps(batches, indent=1), encoding="utf-8"
        )
        print(f"{name}: {len(ids)} variants in {len(batches)} batches")
    (HERE / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
