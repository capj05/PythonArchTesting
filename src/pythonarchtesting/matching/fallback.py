"""Pairing by name where the scores leave an entity unpaired.

A solution that names its modules differently from the reference loses the
module part of the score and the structural part when its bodies differ, so
an entry function with the reference's name and arity can score 0.27 and stay
unpaired although it is the only candidate (E2). Two rules pair such
entities (measured in ``example/matching_weights``):

1. *unique name*: a top-level class or function the scores left with no
   usable candidate is paired with the only top-level target entity of its
   kind and name, when the reference has no other entity of that name. A
   function must accept the reference's positional arguments; a class must
   have every ordinary method the reference's class defines (special methods
   such as a dataclass's generated ``__init__`` are not required), and none of those may
   already be paired with another class's methods. Never a module (a renamed
   module needs an assisted mapping) and never a method (the only method of
   a name may be a base class's);
2. *member of a paired class*: a method the scores did not match is paired
   with the method of the same name and a compatible signature of the target
   class its class was paired with. Inside a paired class the name is the
   stronger evidence: a weak best candidate (``low_confidence``,
   ``ambiguous``) in another class, or a sibling method's, gives way.

The scores keep the last word otherwise: a match is never replaced or
taken; under rule 1 an entity whose best candidate is another target keeps
it, and a target that another unmatched entity scores best for goes to the
higher score. A pair made here names its target first among the candidates, with
the confidence the scores gave it (0 when they never considered it), and
says which rule made it (``unique_name`` / ``member_of_paired_class``).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional

from pythonarchtesting.entities import Entity, EntityIndex

from .assisted import signature_compatible
from .models import Candidate, MatchResult, MatchStatus

_CALLABLE = {"function", "method"}
# Codes of the pairs made here: an assisted mapping may replace them.
FALLBACK_CODES = ("unique_name", "member_of_paired_class")


def is_fallback_pair(match: MatchResult) -> bool:
    """Whether ``match`` was paired by name rather than by the scores."""
    return match.status == MatchStatus.MATCHED and any(
        reason.get("code") in FALLBACK_CODES for reason in match.reasons
    )


def _accepts(source: Entity, target: Entity) -> bool:
    return source.kind not in _CALLABLE or signature_compatible(
        source.signature, target.signature
    )


def _paired(match: MatchResult, target: Entity, code: str, message: str) -> MatchResult:
    scored = next(
        (c for c in match.candidates if c.target_id == target.canonical_id), None
    )
    first = scored or Candidate(
        target_id=target.canonical_id,
        confidence=0.0,
        breakdown={"name": 1.0},
        tie_break=(),
    )
    return replace(
        match,
        status=MatchStatus.MATCHED,
        target_id=target.canonical_id,
        confidence=first.confidence,
        candidates=[first, *(c for c in match.candidates if c is not scored)],
        reasons=[
            *match.reasons,
            {
                "code": code,
                "message": message,
                "evidence": {
                    "previous_status": match.status.value,
                    "target_id": target.canonical_id,
                },
            },
        ],
    )


def _open_for(match: MatchResult, target: Entity) -> bool:
    """Whether the scores leave ``match`` free to take ``target``."""
    if match.status == MatchStatus.MATCHED:
        return False
    if match.status == MatchStatus.UNMATCHED or not match.candidates:
        return True
    # low_confidence / ambiguous: only when the scores' best is this target.
    return match.candidates[0].target_id == target.canonical_id


def _dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _top_level(entity: Entity) -> bool:
    return "." not in entity.qualname


def _methods(index: EntityIndex, module: str, owner: str) -> list[Entity]:
    prefix = f"{owner}."
    return [
        e
        for e in index.all_sorted
        if e.kind == "method"
        and e.module_path == module
        and e.qualname.startswith(prefix)
        and "." not in e.qualname[len(prefix) :]
    ]


def pair_by_name(
    results: List[MatchResult],
    by_source: Dict[str, MatchResult],
    source_index: EntityIndex,
    target_index: EntityIndex,
) -> tuple[List[MatchResult], Dict[str, MatchResult]]:
    """``results`` with the unpaired entities the two rules can pair, paired."""
    # Targets the scores give to someone: matches, and for an entity left
    # without one, its best candidate (the highest-scoring claim wins).
    taken = {
        m.target_id
        for m in results
        if m.status == MatchStatus.MATCHED and m.target_id is not None
    }
    claims: dict[str, tuple[float, str]] = {}
    for m in results:
        if m.status == MatchStatus.MATCHED or not m.candidates:
            continue
        best = m.candidates[0]
        held = claims.get(best.target_id)
        if held is None or (best.confidence, m.source_id) > held:
            claims[best.target_id] = (best.confidence, m.source_id)
    by_source = dict(by_source)
    targets = {e.canonical_id: e for e in target_index.all_sorted}

    def free(target: Entity, match: MatchResult) -> bool:
        if not _open_for(match, target) or target.canonical_id in taken:
            return False
        claim = claims.get(target.canonical_id)
        return claim is None or claim[1] == match.source_id

    def class_fits(source: Entity, target: Entity) -> bool:
        # Special methods may be generated (a dataclass's __init__, __eq__),
        # so only the ordinary ones are required.
        wanted = [
            m
            for m in _methods(source_index, source.module_path, source.qualname)
            if not _dunder(m.qualname.rpartition(".")[2])
        ]
        offered = {
            e.qualname.rpartition(".")[2]
            for e in _methods(target_index, target.module_path, target.qualname)
        }
        if any(m.qualname.rpartition(".")[2] not in offered for m in wanted):
            return False
        for method in wanted:
            paired = by_source.get(method.canonical_id)
            if paired is None or paired.status != MatchStatus.MATCHED:
                continue
            owner = targets.get(paired.target_id or "")
            if owner is not None and (
                owner.module_path != target.module_path
                or owner.qualname.rpartition(".")[0] != target.qualname
            ):
                return False
        return True

    for source in source_index.all_sorted:
        if source.kind not in ("class", "function") or not _top_level(source):
            continue
        match = by_source.get(source.canonical_id)
        if match is None:
            continue
        if len(source_index.by_name.get((source.kind, source.name), [])) != 1:
            continue
        pool = [
            e
            for e in target_index.by_name.get((source.kind, source.name), [])
            if _top_level(e)
        ]
        if len(pool) != 1:
            continue
        target = pool[0]
        if not free(target, match) or not _accepts(source, target):
            continue
        if source.kind == "class" and not class_fits(source, target):
            continue
        by_source[source.canonical_id] = _paired(
            match,
            target,
            "unique_name",
            f"the only {source.kind} named {source.name} in the target",
        )
        taken.add(target.canonical_id)

    class_pairs: dict[tuple[str, str], Entity] = {}
    for source in source_index.all_sorted:
        match = by_source.get(source.canonical_id)
        if source.kind != "class" or match is None:
            continue
        if match.status == MatchStatus.MATCHED and match.target_id in targets:
            class_pairs[(source.module_path, source.qualname)] = targets[
                match.target_id
            ]
    for source in source_index.all_sorted:
        if source.kind != "method":
            continue
        match = by_source.get(source.canonical_id)
        if match is None or match.status == MatchStatus.MATCHED:
            continue
        owner, _, name = source.qualname.rpartition(".")
        paired_class = class_pairs.get((source.module_path, owner))
        if paired_class is None:
            continue
        # Every method of that name (a property's getter and setter share it).
        member: Optional[Entity] = next(
            (
                e
                for e in target_index.all_sorted
                if e.kind == "method"
                and e.module_path == paired_class.module_path
                and e.qualname == f"{paired_class.qualname}.{name}"
                and e.canonical_id not in taken
                and _accepts(source, e)
            ),
            None,
        )
        if member is None:
            continue
        by_source[source.canonical_id] = _paired(
            match,
            member,
            "member_of_paired_class",
            f"method {name} of {paired_class.qualname}, the pair of its class",
        )
        taken.add(member.canonical_id)

    paired = [by_source.get(m.source_id, m) for m in results]
    return paired, {m.source_id: m for m in paired}


__all__ = ["FALLBACK_CODES", "is_fallback_pair", "pair_by_name"]
