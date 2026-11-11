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


def _taken(results: List[MatchResult]) -> set[str]:
    """The targets the scores matched, which no rule here may take again."""
    return {
        m.target_id
        for m in results
        if m.status == MatchStatus.MATCHED and m.target_id is not None
    }


def _claims(results: List[MatchResult]) -> dict[str, tuple[float, str]]:
    """For each target, the unpaired entity that scores best for it.

    An entity left without a match claims its best candidate. When several
    claim one target, the higher ``(confidence, source_id)`` wins, so a tie in
    confidence goes to the larger source id whatever the order of ``results``.
    """
    claims: dict[str, tuple[float, str]] = {}
    for m in results:
        if m.status == MatchStatus.MATCHED or not m.candidates:
            continue
        best = m.candidates[0]
        held = claims.get(best.target_id)
        if held is None or (best.confidence, m.source_id) > held:
            claims[best.target_id] = (best.confidence, m.source_id)
    return claims


def _free(
    target: Entity,
    match: MatchResult,
    taken: set[str],
    claims: dict[str, tuple[float, str]],
) -> bool:
    """Whether rule 1 may give ``target`` to ``match``.

    The scores keep the last word: the target must be open for the match, not
    yet taken, and claimed by nobody else.
    """
    if not _open_for(match, target) or target.canonical_id in taken:
        return False
    claim = claims.get(target.canonical_id)
    return claim is None or claim[1] == match.source_id


def _class_fits(
    source: Entity,
    target: Entity,
    indexes: tuple[EntityIndex, EntityIndex],
    by_source: Dict[str, MatchResult],
    targets: Dict[str, Entity],
) -> bool:
    """Whether the target class has every ordinary method of the reference's.

    Special methods may be generated (a dataclass's ``__init__``, ``__eq__``),
    so only the ordinary ones are required. A required method already paired
    with a method of another class rules the target class out.
    """
    source_index, target_index = indexes
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


def _unique_target(
    source: Entity, source_index: EntityIndex, target_index: EntityIndex
) -> Optional[Entity]:
    """The only top-level target of the source's kind and name, if any.

    ``None`` as well when the reference has another entity of that kind and
    name, since the name then no longer identifies the source.
    """
    if len(source_index.by_name.get((source.kind, source.name), [])) != 1:
        return None
    pool = [
        e
        for e in target_index.by_name.get((source.kind, source.name), [])
        if _top_level(e)
    ]
    return pool[0] if len(pool) == 1 else None


def _pair_unique_names(
    by_source: Dict[str, MatchResult],
    indexes: tuple[EntityIndex, EntityIndex],
    taken: set[str],
    claims: dict[str, tuple[float, str]],
    targets: Dict[str, Entity],
) -> None:
    """Apply rule 1 (*unique name*) to ``by_source`` in place.

    Sources are visited in the order of ``all_sorted`` and every pair made
    adds its target to ``taken``, so an earlier source wins a target that a
    later one could also take.
    """
    source_index, target_index = indexes
    for source in source_index.all_sorted:
        if source.kind not in ("class", "function") or not _top_level(source):
            continue
        match = by_source.get(source.canonical_id)
        if match is None:
            continue
        target = _unique_target(source, source_index, target_index)
        if target is None:
            continue
        if not _free(target, match, taken, claims) or not _accepts(source, target):
            continue
        if source.kind == "class" and not _class_fits(
            source, target, indexes, by_source, targets
        ):
            continue
        by_source[source.canonical_id] = _paired(
            match,
            target,
            "unique_name",
            f"the only {source.kind} named {source.name} in the target",
        )
        taken.add(target.canonical_id)


def _class_pairs(
    by_source: Dict[str, MatchResult],
    source_index: EntityIndex,
    targets: Dict[str, Entity],
) -> dict[tuple[str, str], Entity]:
    """The target class each matched reference class is paired with.

    Keyed by the reference class's module and qualname, which is how a method
    finds its class.
    """
    class_pairs: dict[tuple[str, str], Entity] = {}
    for source in source_index.all_sorted:
        match = by_source.get(source.canonical_id)
        if source.kind != "class" or match is None:
            continue
        if match.status == MatchStatus.MATCHED and match.target_id in targets:
            class_pairs[(source.module_path, source.qualname)] = targets[
                match.target_id
            ]
    return class_pairs


def _member(
    source: Entity,
    name: str,
    paired_class: Entity,
    target_index: EntityIndex,
    taken: set[str],
) -> Optional[Entity]:
    """The first free method ``name`` of ``paired_class`` the source fits.

    Every method of that name is considered, because a property's getter and
    setter share it.
    """
    return next(
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


def _pair_members(
    by_source: Dict[str, MatchResult],
    indexes: tuple[EntityIndex, EntityIndex],
    taken: set[str],
    class_pairs: dict[tuple[str, str], Entity],
) -> None:
    """Apply rule 2 (*member of a paired class*) to ``by_source`` in place.

    Every pair made adds its target to ``taken``, so two reference methods
    never share one target method.
    """
    source_index, target_index = indexes
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
        member = _member(source, name, paired_class, target_index, taken)
        if member is None:
            continue
        by_source[source.canonical_id] = _paired(
            match,
            member,
            "member_of_paired_class",
            f"method {name} of {paired_class.qualname}, the pair of its class",
        )
        taken.add(member.canonical_id)


def pair_by_name(
    results: List[MatchResult],
    by_source: Dict[str, MatchResult],
    source_index: EntityIndex,
    target_index: EntityIndex,
) -> tuple[List[MatchResult], Dict[str, MatchResult]]:
    """``results`` with the unpaired entities the two rules can pair, paired.

    The rules run in order on one copy of ``by_source`` and one set of taken
    targets, so rule 2 sees the classes rule 1 paired and neither rule hands
    out a target twice.
    """
    # Targets the scores give to someone: matches, and for an entity left
    # without one, its best candidate (the highest-scoring claim wins).
    taken = _taken(results)
    claims = _claims(results)
    by_source = dict(by_source)
    targets = {e.canonical_id: e for e in target_index.all_sorted}
    indexes = (source_index, target_index)
    _pair_unique_names(by_source, indexes, taken, claims, targets)
    class_pairs = _class_pairs(by_source, source_index, targets)
    _pair_members(by_source, indexes, taken, class_pairs)
    paired = [by_source.get(m.source_id, m) for m in results]
    return paired, {m.source_id: m for m in paired}


__all__ = ["FALLBACK_CODES", "is_fallback_pair", "pair_by_name"]
