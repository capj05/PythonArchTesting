"""The data of global mode: which entities play a principle's roles, and the
outcome of one principle for one submission.

Entity names are relative to the submission root, as the core names them
(``actions.status``, ``ship.Cargo``, ``ui.main``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Optional

Source = Literal["code", "ai", "teacher"]
Status = Literal["not_applied", "ok", "unverified", "violated"]


@dataclass(frozen=True)
class BoundEntity:
    """An entity bound to a role: who bound it (the discovery predicate, the
    AI client or the teacher) and why. ``disputed`` is the AI's reason to
    doubt a candidate it may not remove; its findings are flagged, the
    verdict stays with the code."""

    entity: str
    source: Source
    why: str
    disputed: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "entity": self.entity,
            "source": self.source,
            "why": self.why,
        }
        if self.disputed is not None:
            data["disputed"] = self.disputed
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BoundEntity:
        """The entity ``to_dict`` wrote."""
        return cls(
            entity=str(data["entity"]),
            source=data["source"],
            why=str(data["why"]),
            disputed=data.get("disputed"),
        )


def _roles_dict(
    roles: Mapping[str, tuple[BoundEntity, ...]],
) -> dict[str, list[dict[str, Any]]]:
    return {role: [e.to_dict() for e in bound] for role, bound in roles.items()}


@dataclass(frozen=True)
class RoleDiscovery:
    """The roles of one principle found in a submission. ``conflicts`` names
    entities that fit two roles; ``not_applied`` says why the principle does
    not apply (a role it cannot do without has no candidate), else ``None``."""

    principle: str
    roles: Mapping[str, tuple[BoundEntity, ...]]
    conflicts: tuple[str, ...]
    not_applied: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "principle": self.principle,
            "roles": _roles_dict(self.roles),
            "conflicts": list(self.conflicts),
            "not_applied": self.not_applied,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RoleDiscovery:
        """The discovery ``to_dict`` wrote (``discovery.json`` of a global
        task)."""
        return cls(
            principle=str(data["principle"]),
            roles={
                str(role): tuple(BoundEntity.from_dict(b) for b in bound)
                for role, bound in data["roles"].items()
            },
            conflicts=tuple(str(c) for c in data["conflicts"]),
            not_applied=data.get("not_applied"),
        )


@dataclass(frozen=True)
class PrincipleOutcome:
    """The result of one principle for one submission.

    ``sites`` counts the bound entities with a check, ``violations`` those
    with a finding; ``coverage`` and ``mutation`` (error id -> status of its
    mutation check) are ``None`` when they were not computed.
    ``unclassified`` lists failed results no typical error explains (a write
    to any foreign project object): shown to the teacher, but they do not
    change ``status``. ``unexercised`` lists, per checked entity, the lines
    of it no case ran (``entity``, ``file``, ``lines``), whatever the status:
    an ``ok`` says nothing about them."""

    principle: str
    status: Status
    roles: Mapping[str, tuple[BoundEntity, ...]]
    findings: tuple[dict[str, Any], ...]
    unverified: tuple[dict[str, Any], ...]
    coverage: Optional[float]
    mutation: Optional[Mapping[str, str]]
    sites: int
    violations: int
    unclassified: tuple[dict[str, Any], ...] = ()
    unexercised: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "principle": self.principle,
            "status": self.status,
            "roles": _roles_dict(self.roles),
            "sites": self.sites,
            "ok": max(self.sites - self.violations, 0),
            "violations": self.violations,
            "findings": [dict(f) for f in self.findings],
            "coverage": self.coverage,
            "unverified": [dict(u) for u in self.unverified],
            "mutation": dict(self.mutation) if self.mutation is not None else None,
            "unclassified": [dict(u) for u in self.unclassified],
            "unexercised": [dict(u) for u in self.unexercised],
        }


__all__ = ["BoundEntity", "PrincipleOutcome", "RoleDiscovery"]
