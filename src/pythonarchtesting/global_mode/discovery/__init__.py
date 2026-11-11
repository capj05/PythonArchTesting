"""Role discovery: which entities of a submission play a principle's roles.

Each principle has deterministic predicates over the AST the core extracts
(``Entity.extras["ast_node"]``); nothing of the submission runs. Every
candidate a predicate finds is bound, with the source ``code`` and a short
reason. The AI client then may only (design § 5.2):

- ``add`` an entity the predicates missed (source ``ai``);
- ``dispute`` a candidate: it stays bound, ``disputed`` holds the AI's
  reason, and the teacher decides on its findings. A candidate is never
  removed, since removing it would remove its checks;
- ``move`` an entity from ``io`` to ``logic`` of ``io_separation`` (a game
  action that reads the keyboard, ``input_in_logic``). The move is accepted
  only when some code of the project outside the function's own body refers
  to it (an entry point or a dispatcher calls it); else it stays ``io``.

``overrides`` maps a role to the overrides about it: the role an entity is
added to or disputed in, or moved from (``Override.to_role`` is the target).
An override the rules do not allow, or one naming an entity the submission
does not have, changes nothing and is listed in ``conflicts``, as is an
entity bound to more than one role of the principle (it stays in each).

The project's tests are no part of the program a principle is about:
discovery skips every module named ``test_*.py``, ``*_test.py`` or
``conftest.py`` and everything under a directory named ``tests`` or
``test`` (``_ast.is_test_module``). The AI may still ``add`` an entity of a
test; a reference from a test does not justify a ``move``.

A role the principle cannot do without (``ESSENTIAL_ROLES``) with no entity
makes the principle not applied: ``not_applied`` says which role is missing
and why, naming the typical error that hides the role from its predicate.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Optional

from pythonarchtesting.entities import Entity
from pythonarchtesting.global_mode.discovery import (
    encapsulation,
    io_separation,
    polymorphism,
)
from pythonarchtesting.global_mode.discovery._ast import (
    name_of,
    project_entities,
    references_outside,
)
from pythonarchtesting.global_mode.discovery.polymorphism import split_by_base
from pythonarchtesting.global_mode.model import BoundEntity, RoleDiscovery
from pythonarchtesting.principles.catalog import Principle, get_principle

ESSENTIAL_ROLES: Mapping[str, tuple[str, ...]] = {
    "io_separation": ("io", "logic"),
    "polymorphism": ("base", "variant"),
    "encapsulation": ("owner",),
    "strategy": ("context", "strategy"),
}

Action = Literal["add", "dispute", "move"]
_ACTIONS = ("add", "dispute", "move")
# The one move the rules allow: (principle, from role, to role).
_MOVE = ("io_separation", "io", "logic")


@dataclass(frozen=True)
class Override:
    """The AI client's correction of one binding (module docstring)."""

    entity: str
    action: Action
    to_role: Optional[str]
    why: str


Finder = Callable[[Sequence[Entity]], Mapping[str, Sequence[BoundEntity]]]


@dataclass(frozen=True)
class Predicates:
    """The discovery of one principle: ``find`` returns the candidates per
    role; ``not_found`` explains an empty role; ``hidden_by`` names the
    typical error that may be why a role is empty."""

    find: Finder
    not_found: Mapping[str, str]
    hidden_by: Mapping[str, str] = dataclasses.field(default_factory=dict)


_REGISTRY: dict[str, Predicates] = {
    "io_separation": Predicates(
        io_separation.find, io_separation.NOT_FOUND, io_separation.HIDDEN_BY
    ),
    "polymorphism": Predicates(
        polymorphism.find, polymorphism.NOT_FOUND, polymorphism.HIDDEN_BY
    ),
    "encapsulation": Predicates(
        encapsulation.find, encapsulation.NOT_FOUND, encapsulation.HIDDEN_BY
    ),
}


def _describe(override: Override, role: str) -> str:
    if override.action == "add":
        return f"add of {override.entity} to {role}"
    if override.action == "move":
        return f"move of {override.entity} from {role} to {override.to_role}"
    return f"{override.action} of {override.entity} in {role}"


def _apply(
    principle: str,
    role: str,
    override: Override,
    roles: dict[str, dict[str, BoundEntity]],
    entities: Sequence[Entity],
) -> Optional[str]:
    """Apply one override to ``roles``; the conflict it raises, if any.
    ``entities`` are all of the submission, its tests included."""
    what = _describe(override, role)
    if override.action not in _ACTIONS:
        return f"{what} ignored: an override may only add, dispute or move an entity"
    if role not in roles:
        return f"{what} ignored: {principle} has no role {role}"
    matching = [e for e in entities if name_of(e) == override.entity]
    if not matching:
        return f"{what} ignored: the submission has no such entity"
    bound = roles[role]
    if override.action == "add":
        if override.entity not in bound:
            bound[override.entity] = BoundEntity(override.entity, "ai", override.why)
        return None
    if override.entity not in bound:
        return f"{what} ignored: {override.entity} is not bound to {role}"
    if override.action == "dispute":
        bound[override.entity] = dataclasses.replace(
            bound[override.entity], disputed=override.why
        )
        return None
    if (principle, role, override.to_role) != _MOVE:
        return (
            f"{what} rejected: only a move from io to logic of io_separation "
            "is allowed"
        )
    program = project_entities(entities)
    if not any(references_outside(e, program) for e in matching):
        return (
            f"{what} rejected: nothing in the project refers to it outside its "
            "own body"
        )
    del bound[override.entity]
    roles[_MOVE[2]][override.entity] = BoundEntity(override.entity, "ai", override.why)
    return None


def _not_applied(
    entry: Principle,
    predicates: Predicates,
    roles: Mapping[str, tuple[BoundEntity, ...]],
) -> Optional[str]:
    for role in ESSENTIAL_ROLES.get(entry.id, ()):
        if roles.get(role):
            continue
        text = f"{role} not found: {predicates.not_found.get(role, 'no candidate')}"
        error_id = predicates.hidden_by.get(role)
        titles = {e.id: e.title for e in entry.errors}
        if error_id in titles:
            text += f" (perhaps typical error {error_id}: {titles[error_id]})"
        return text
    return None


def discover_roles(
    principle: str,
    entities: Sequence[Entity],
    overrides: Mapping[str, Sequence[Override]] | None = None,
) -> RoleDiscovery:
    """The roles of ``principle`` in the submission whose core entities are
    ``entities`` (``prepare_source(...).source_entities``), after the AI's
    ``overrides`` (module docstring). Deterministic: each role is sorted by
    entity name and ``conflicts`` is sorted. Raises ``UnknownPrincipleError``
    for a principle not in the catalogue and ``ValueError`` for one that has
    no discovery yet."""
    entry = get_principle(principle)
    predicates = _REGISTRY.get(principle)
    if predicates is None:
        raise ValueError(f"principle {principle!r} has no role discovery yet")
    found = predicates.find(project_entities(entities))
    roles: dict[str, dict[str, BoundEntity]] = {
        role: {b.entity: b for b in found.get(role, ())} for role in entry.roles
    }
    conflicts: set[str] = set()
    for role in sorted(overrides or {}):
        for override in (overrides or {})[role]:
            conflict = _apply(principle, role, override, roles, entities)
            if conflict is not None:
                conflicts.add(conflict)

    playing: dict[str, list[str]] = {}
    for role in sorted(roles):
        for name in roles[role]:
            playing.setdefault(name, []).append(role)
    conflicts.update(
        f"{name} fits more than one role: {', '.join(in_roles)}"
        for name, in_roles in playing.items()
        if len(in_roles) > 1
    )
    final = {
        role: tuple(sorted(bound.values(), key=lambda b: b.entity))
        for role, bound in roles.items()
    }
    return RoleDiscovery(
        principle=principle,
        roles=final,
        conflicts=tuple(sorted(conflicts)),
        not_applied=_not_applied(entry, predicates, final),
    )


__all__ = [
    "ESSENTIAL_ROLES",
    "Override",
    "Predicates",
    "discover_roles",
    "split_by_base",
]
