"""Measure variants of the automatic matching against known pairings.

The decision left open after E2 (docs/dev_notes/evaluation-f5-2026-10-31.md):
should a name match weigh more when it is the only candidate? E2 showed an
entry function with the same name and arity scored 0.27 against a minimum of
0.5 in a solution that names its modules differently, so every runtime rule
of it went unpaired. Raising the name's weight changes the pairing of every
target, so it is measured here first, on every target whose correct pairing
is known:

- the 24 simulated solutions of E2 (``example/llm_solutions/generated``):
  with a skeleton the modules keep the reference's names; without one the
  pairs of renamed modules come from the solution's ``mapping.json``, the
  assisted pairing an LLM wrote and the evaluation confirmed;
- every mutant and equivalent rewrite of both programs, hand-made and
  held-out (``example/architectural_mutants{,_2}``), with their renames;
- the assignments of ``example/checkout_assignment`` and every target of
  ``example/rule_showcase``, which keep the reference's names, so the
  correct pair is the same entity. They hold the traps a name rule can
  fall into, such as a method inherited from a base class.

A reference entity's correct target is the entity of the same kind and
qualified name in the module its module became. An entity whose module was
merged or removed has no known target; it is counted apart.

Variants:

- ``baseline``: the matching as it is;
- ``unique_name``: an entity left unpaired is paired with the only target
  entity of its kind and name, when the target accepts the reference's
  arguments (the assisted-pairing signature check);
- ``unique_name_unchecked``: the same without the signature check;
- ``unique_name_members``: ``unique_name``, then a method still unpaired is
  paired with the method of the same name of its class's pair (signature
  checked);
- ``engine_name_fallback``: the matching with ``[matching] name_fallback``,
  the two rules above as built in (``matching/fallback.py``), which also
  never takes a target entity another reference entity is paired with;
- ``name_weight``: stage 3 weighs the name 0.45 instead of 0.30 and the
  structure 0.40 instead of 0.55.

    python example/matching_weights/measure.py     # writes results.md
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterator

from pythonarchtesting.config import load_config
from pythonarchtesting.config.accessors import get_bool
from pythonarchtesting.entities import Entity, build_entity_index, sort_entities
from pythonarchtesting.entities_extraction import (
    extract_entities_from_ast_with_nonmatchable,
)
from pythonarchtesting.evidence.collection import parse_python_modules
from pythonarchtesting.matching import MatchingConfig, MatchStatus, run_matching
from pythonarchtesting.matching import candidates as candidates_module
from pythonarchtesting.matching import engine as engine_module
from pythonarchtesting.matching.assisted import signature_compatible
from pythonarchtesting.runner.source_prep import prepare_source

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent
PROGRAMS = {
    "program1": EXAMPLES / "architectural_mutants",
    "program2": EXAMPLES / "architectural_mutants_2",
}
_CALLABLE = {"function", "method"}


@dataclass
class Target:
    dataset: str
    name: str
    program: Path
    path: Path
    # Module renames: reference module -> target module.
    renames: dict[str, str] = field(default_factory=dict)


@dataclass
class Tally:
    correct: int = 0
    wrong: int = 0
    missed: int = 0
    no_truth_paired: int = 0
    no_truth_unpaired: int = 0
    wrong_examples: list[str] = field(default_factory=list)
    unverified_examples: list[str] = field(default_factory=list)
    missed_examples: list[str] = field(default_factory=list)
    missed_kinds: Counter[str] = field(default_factory=Counter)

    def add(self, other: "Tally") -> None:
        self.correct += other.correct
        self.wrong += other.wrong
        self.missed += other.missed
        self.no_truth_paired += other.no_truth_paired
        self.no_truth_unpaired += other.no_truth_unpaired
        self.wrong_examples.extend(other.wrong_examples)
        self.unverified_examples.extend(other.unverified_examples)
        self.missed_examples.extend(other.missed_examples)
        self.missed_kinds.update(other.missed_kinds)


def _module(path: str) -> str:
    return path[:-3].replace("/", ".") if path.endswith(".py") else path


def _load_variants(path: Path) -> list[dict[str, Any]]:
    spec = importlib.util.spec_from_file_location(f"variants_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"no {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.MUTANTS) + list(module.EQUIVALENTS)


def _apply(variant: dict[str, Any], root: Path) -> None:
    for old, new in (variant.get("renames") or {}).items():
        (root / old).rename(root / new)
    for name in variant.get("removed_files") or []:
        (root / name).unlink()
    for name, text in (variant.get("new_files") or {}).items():
        (root / name).write_text(text, encoding="utf-8")
    for name, old, new in variant.get("patches", []):
        path = root / name
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise ValueError(f"{variant['id']}: patch does not apply to {name}")
        path.write_text(text.replace(old, new), encoding="utf-8")


def _e2_targets() -> Iterator[Target]:
    generated = EXAMPLES / "llm_solutions" / "generated"
    if not generated.is_dir():
        # The solutions are generated, not versioned (.gitignore).
        print(
            f"warning: {generated} is missing: the E2 datasets are left out; "
            "generate them as example/llm_solutions/README.md describes",
            file=sys.stderr,
        )
        return
    for program, program_dir in PROGRAMS.items():
        for variant in ("skeleton", "text"):
            base = generated / program / variant
            if not base.is_dir():
                continue
            for run in sorted(base.iterdir()):
                renames: dict[str, str] = {}
                mapping = run / "mapping.json"
                if variant == "text" and mapping.is_file():
                    data = json.loads(mapping.read_text(encoding="utf-8"))
                    renames = dict(data.get("pairs") or {})
                yield Target(
                    f"E2 {variant}",
                    f"{program}/{run.name}",
                    program_dir,
                    run / "solution",
                    renames,
                )


def _mutant_targets(scratch: Path) -> Iterator[Target]:
    for program, program_dir in PROGRAMS.items():
        sets = [("mutants (hand)", program_dir / "mutants.py")]
        if (program_dir / "llm_mutants.py").is_file():
            sets.append(("mutants (held-out)", program_dir / "llm_mutants.py"))
        for label, path in sets:
            for variant in _load_variants(path):
                root = scratch / program / label.split()[1].strip("()") / variant["id"]
                shutil.copytree(program_dir / "solution", root)
                try:
                    _apply(variant, root)
                except (ValueError, OSError):
                    continue
                renames = {
                    _module(old): _module(new)
                    for old, new in (variant.get("renames") or {}).items()
                }
                yield Target(
                    label, f"{program}/{variant['id']}", program_dir, root, renames
                )


def _assignment_targets(label: str, roots: list[Path]) -> Iterator[Target]:
    """Targets next to a reference, named as it is: the correct pair is the same entity."""
    for root in roots:
        if not (root / "reference").is_dir():
            continue
        for path in sorted((root / "assignments").glob("*")):
            if path.is_dir():
                yield Target(label, f"{root.name}/{path.name}", root, path)


def _target_index(path: Path, config: Any) -> Any:
    include_nested = get_bool(config, "matching", "include_nested_functions", False)
    parsed_modules, _ = parse_python_modules(
        root_path=path, config=config, target_module_name=None
    )
    entities: list[Entity] = []
    for parsed in parsed_modules:
        matchable, _ = extract_entities_from_ast_with_nonmatchable(
            parsed.tree,
            parsed.file_text,
            parsed.file_path,
            path,
            None,
            role="target",
            include_nested_functions=include_nested,
            root_label="target",
        )
        entities.extend(matchable)
    return build_entity_index(sort_entities(entities))


def _truth(source: Entity, target_index: Any, renames: dict[str, str]) -> Entity | None:
    module = renames.get(source.module_path, source.module_path)
    for entity in target_index.all_sorted:
        if (
            entity.kind == source.kind
            and entity.module_path == module
            and entity.qualname == source.qualname
        ):
            return entity
    return None


def _unique_name(check_signature: bool) -> Callable[[Entity, Any], Entity | None]:
    def pick(source: Entity, target_index: Any) -> Entity | None:
        pool = target_index.by_name.get((source.kind, source.name), [])
        if len(pool) != 1:
            return None
        target = pool[0]
        if (
            check_signature
            and source.kind in _CALLABLE
            and not signature_compatible(source.signature, target.signature)
        ):
            return None
        return target

    return pick


def _pair_members(
    sources: list[Entity], target_index: Any, pairs: dict[str, Entity | None]
) -> None:
    """Pair an unpaired method with the same-named method of its class's pair."""
    classes = {
        (s.module_path, s.qualname): pairs.get(s.canonical_id)
        for s in sources
        if s.kind == "class"
    }
    for source in sources:
        if source.kind != "method" or pairs.get(source.canonical_id) is not None:
            continue
        owner, _, name = source.qualname.rpartition(".")
        paired_class = classes.get((source.module_path, owner))
        if paired_class is None:
            continue
        for target in target_index.all_sorted:
            if (
                target.kind == "method"
                and target.module_path == paired_class.module_path
                and target.qualname == f"{paired_class.qualname}.{name}"
                and signature_compatible(source.signature, target.signature)
            ):
                pairs[source.canonical_id] = target
                break


@contextlib.contextmanager
def _name_weight(name: float, structure: float) -> Iterator[None]:
    original = candidates_module._stage3_candidates

    def reweighted(*args: Any, **kwargs: Any) -> Any:
        found = original(*args, **kwargs)
        changed = []
        for candidate in found:
            b = candidate.breakdown
            structural = 0.70 * b["ast"] + 0.30 * b["mod"]
            confidence = max(
                0.0,
                round(
                    structure * structural
                    + name * b["name"]
                    + 0.15 * b["doc"]
                    - b["penalty"],
                    6,
                ),
            )
            changed.append(replace(candidate, confidence=confidence))
        return candidates_module._sort_candidates(changed)

    engine_module._stage3_candidates = reweighted
    try:
        yield
    finally:
        engine_module._stage3_candidates = original


def _measure(
    target: Target,
    source_state: Any,
    config: Any,
    variant: str,
) -> Tally:
    target_index = _target_index(target.path, config)
    # The emulated variants start from the scores alone.
    matching = replace(
        MatchingConfig.from_config(config),
        name_fallback=variant == "engine_name_fallback",
    )
    context = (
        _name_weight(0.45, 0.40)
        if variant == "name_weight"
        else contextlib.nullcontext()
    )
    with context:
        _, by_source = run_matching(source_state.source_index, target_index, matching)
    fallback = {
        "unique_name": _unique_name(True),
        "unique_name_unchecked": _unique_name(False),
        "unique_name_members": _unique_name(True),
    }.get(variant)
    by_id = {e.canonical_id: e for e in target_index.all_sorted}
    sources = source_state.source_index.all_sorted
    pairs: dict[str, Entity | None] = {}
    for source in sources:
        match = by_source.get(source.canonical_id)
        paired = (
            by_id.get(match.target_id)
            if match is not None and match.status == MatchStatus.MATCHED
            else None
        )
        if paired is None and fallback is not None:
            paired = fallback(source, target_index)
        pairs[source.canonical_id] = paired
    if variant == "unique_name_members":
        _pair_members(sources, target_index, pairs)
    tally = Tally()
    for source in sources:
        paired = pairs[source.canonical_id]
        truth = _truth(source, target_index, target.renames)
        if truth is None:
            if paired is None:
                tally.no_truth_unpaired += 1
            else:
                tally.no_truth_paired += 1
                tally.unverified_examples.append(
                    f"{target.name}: {source.kind} {source.module_path}:{source.qualname} "
                    f"-> {paired.module_path}:{paired.qualname}"
                )
        elif paired is None:
            tally.missed += 1
            tally.missed_kinds[source.kind] += 1
            tally.missed_examples.append(
                f"{target.name}: {source.kind} {source.module_path}:{source.qualname}"
            )
        elif paired.canonical_id == truth.canonical_id:
            tally.correct += 1
        else:
            tally.wrong += 1
            tally.wrong_examples.append(
                f"{target.name}: {source.module_path}:{source.qualname} -> "
                f"{paired.module_path}:{paired.qualname} "
                f"(expected {truth.module_path}:{truth.qualname})"
            )
    return tally


VARIANTS = (
    "baseline",
    "unique_name",
    "unique_name_unchecked",
    "unique_name_members",
    "engine_name_fallback",
    "name_weight",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", type=Path, default=HERE / "results.md")
    args = parser.parse_args()
    config = load_config(config_path=None, cli_args={}, discover_from_cwd=False)
    showcase = sorted(p for p in (EXAMPLES / "rule_showcase").iterdir() if p.is_dir())
    assignment_roots = [EXAMPLES / "checkout_assignment", *showcase]
    states = {
        path: prepare_source(config=config, source_path=path / "reference")
        for path in [*PROGRAMS.values(), *assignment_roots]
        if (path / "reference").is_dir()
    }
    totals: dict[tuple[str, str], Tally] = {}
    per_target: dict[tuple[str, str], dict[str, Tally]] = {}
    with tempfile.TemporaryDirectory() as scratch:
        targets = (
            list(_e2_targets())
            + list(_mutant_targets(Path(scratch)))
            + list(_assignment_targets("checkout assignment", [assignment_roots[0]]))
            + list(_assignment_targets("rule showcase", showcase))
        )
        for target in targets:
            for variant in VARIANTS:
                tally = _measure(target, states[target.program], config, variant)
                totals.setdefault((target.dataset, variant), Tally()).add(tally)
                per_target.setdefault((target.dataset, target.name), {})[
                    variant
                ] = tally
    datasets = sorted({dataset for dataset, _ in totals})
    lines = [
        "# Matching variants against known pairings",
        "",
        "Generated by `measure.py`; see its docstring for the setup. Counts are "
        "reference entities: paired with their correct target, paired with "
        "another (wrong), left unpaired although a correct target exists "
        "(missed), and those whose module was merged or removed (no known "
        "target), paired or not.",
        "",
        "| Dataset | Targets | Variant | Correct | Wrong | Missed | No target, paired | No target, unpaired |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for dataset in datasets:
        count = sum(1 for d, _ in per_target if d == dataset)
        for variant in VARIANTS:
            t = totals[(dataset, variant)]
            lines.append(
                f"| {dataset} | {count} | {variant} | {t.correct} | {t.wrong} | "
                f"{t.missed} | {t.no_truth_paired} | {t.no_truth_unpaired} |"
            )
    lines.extend(["", "## Wrong pairings", ""])
    for dataset in datasets:
        for variant in VARIANTS:
            for example in totals[(dataset, variant)].wrong_examples:
                lines.append(f"- {dataset}, {variant}: {example}")
    lines.extend(["", "## Paired without a known target (judged by hand)", ""])
    for dataset in datasets:
        for variant in VARIANTS:
            for example in totals[(dataset, variant)].unverified_examples:
                lines.append(f"- {dataset}, {variant}: {example}")
    lines.extend(["", "## Missed, by kind", ""])
    for dataset in datasets:
        for variant in VARIANTS:
            kinds = totals[(dataset, variant)].missed_kinds
            if kinds:
                listed = ", ".join(f"{k} {n}" for k, n in sorted(kinds.items()))
                lines.append(f"- {dataset}, {variant}: {listed}")
                missed = totals[(dataset, variant)].missed_examples
                if len(missed) <= 15:
                    lines.extend(f"  - {example}" for example in missed)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[: 10 + len(datasets) * len(VARIANTS)]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
