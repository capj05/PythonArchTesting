"""The catalogue of teaching principles: loading, validation and the data model.

Every ``catalog/<id>.toml`` holds one principle: what it means and why it
matters, the roles of a task's code, the checks (marker per role), its typical
errors and the changes that must not count as errors. The file format is
described at the top of ``catalog/io_separation.toml``. Loading validates every
entry and raises ``CatalogError`` naming the file and the problem.
"""

from __future__ import annotations

import re
import string
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Optional

from pythonarchtesting.entities_extraction.annotations import (
    SUPPORTED_MARKER_NAMES as MARKERS,
)
from pythonarchtesting.mutation.operators import OPERATORS

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib

CATALOG_DIR = Path(__file__).with_name("catalog")

# The kind of fact each marker an error can be ``detected_by`` reports first;
# an error's ``signature`` names one of these kinds.
MARKER_FACT_KINDS: Mapping[str, str] = MappingProxyType(
    {
        "forbid_runtime_calls": "call",
        "require_runtime_calls": "missing_call",
        "forbid_foreign_writes": "write",
        "forbid_private_access": "read",
        "subclass_of": "not_subclass",
        "is_abstract_class": "not_abstract",
        "require_runtime_delegation": "missing_delegation",
        "forbid_runtime_instantiation": "instance",
    }
)
FACT_KINDS = tuple(MARKER_FACT_KINDS.values())
# Markers checked statically, without running code: their checks take no
# ``cases``, and a task gives the entities they cover none.
STATIC_MARKERS = frozenset(
    {"forbid_private_access", "subclass_of", "is_abstract_class"}
)
# Markers whose entities are classes: a role they cover binds classes only.
CLASS_MARKERS = frozenset({"subclass_of", "is_abstract_class"})
# The one marker that takes a class as its target (``target_kind = "class"``).
CLASS_TARGET_MARKERS = frozenset({"subclass_of"})
# Markers whose ``target_role`` gives the classes bound to that role, not
# their modules: the objects a context must not build are the strategy
# classes, not anything else their module defines. A role that binds no
# class gives such a check no target: it is not applicable.
INSTANCE_TARGET_MARKERS = frozenset({"forbid_runtime_instantiation"})
# What a check's ``target_role`` gives its marker: the modules of the
# entities bound to that role, or the one class bound to it.
TARGET_KINDS = ("module", "class")
# The ways a ``write`` fact changes an attribute.
WRITE_CHANGES = ("assigned", "mutated", "deleted", "bypassed")
# What each key of an error's ``signature`` means.
SIGNATURE_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "kind": "the kind of the first fact: " + ", ".join(FACT_KINDS),
        "callee": "of a call: the function called, as 'module:name'",
        "change": "of a write: how the attribute changed: " + ", ".join(WRITE_CHANGES),
        "via": "the call, write or instance took a detour through other code "
        "(a helper)",
        "private": "of a write: the attribute written starts with '_'",
    }
)
# Placeholders an error's ``what`` may use, and what each stands for: the
# target's function, the first fact of the failed result, and three derived
# from it.
PLACEHOLDERS: Mapping[str, str] = MappingProxyType(
    {
        "function": "the function the failed rule is about",
        "file": "the file of that function",
        "line": "the line that function starts on",
        "caller": "the function that made the call or write",
        "callee": "the function called, as 'module:name'",
        "module": "the module whose functions a required call should reach",
        "class": "of a write or read: the class of the object written to or read "
        "from; else the class concerned, as 'module:Class' (the one not derived "
        "from the base, not abstract, or instantiated)",
        "attribute": "the attribute written or read",
        "change": "how the attribute changed, in words",
        "fact_file": "the file of the call, write or read",
        "fact_line": "the line of the call, write or read",
        "callee_short": "the callee as a beginner writes it: print(), input(), "
        "open(), else module.name()",
        "via_last": "the helper a detour ends in, as 'module:name'",
        "via_first_line": "the line of the function the detour starts at",
        "expected_base": "the base class a class should derive from, as "
        "'module:Class'",
        "concrete_methods": "the methods a class that should be abstract "
        "defines without an abstract decorator, comma-separated",
        "creator": "the function that created the object, as 'module:name'",
        "expected": "the collaborator (or 'collaborator.method') never " "delegated to",
    }
)

# A sentence ends at ., ! or ? followed by space, but not at "e.g." / "i.e.".
_SENTENCE_END = re.compile(r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<=[.!?])\s+")
_DOTTED = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
_DOTTED_NAME = re.compile(_DOTTED)
_CALLEE = re.compile(f"{_DOTTED}:{_DOTTED}")


class CatalogError(ValueError):
    """A catalogue entry is malformed."""


class UnknownPrincipleError(LookupError):
    """No principle of the catalogue has the id asked for."""

    def __init__(self, principle_id: str, known: list[str]) -> None:
        super().__init__(
            f"unknown principle {principle_id!r}; known principles: {', '.join(known)}"
        )
        self.principle_id = principle_id
        self.known = known


def _compact(data: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


@dataclass(frozen=True)
class ErrorSignature:
    """What tells a typical error from the others of its marker: the first fact
    of the failed result reduced to its kind, the callee of a call, the change
    of a write, whether the call took a detour (``via``) and whether the
    attribute written is private."""

    kind: str
    via: Optional[bool] = None
    callee: Optional[str] = None
    change: Optional[str] = None
    private: Optional[bool] = None

    def as_dict(self) -> dict[str, Any]:
        """The set fields, in the shape of ``fact_signature``."""
        return _compact(
            {
                "kind": self.kind,
                "callee": self.callee,
                "change": self.change,
                "via": self.via,
                "private": self.private,
            }
        )


@dataclass(frozen=True)
class CheckTemplate:
    """Which marker covers a role of the task, and what its cases must exercise.

    The marker's targets are ``modules`` (fixed dotted names, such as
    ``builtins.print``) and, with ``target_role``, the modules of the entities
    playing that role in the task; with ``target_kind`` ``"class"`` instead
    the qualified name of the one class bound to that role. ``cases`` says
    what the cases of each covered entity must exercise; ``None`` for a
    static marker (``STATIC_MARKERS``), which runs nothing."""

    role: str
    marker: str
    cases: Optional[str]
    modules: tuple[str, ...] = ()
    target_role: Optional[str] = None
    transitive: Optional[bool] = None
    target_kind: str = "module"

    def to_dict(self) -> dict[str, Any]:
        data = {
            "role": self.role,
            "marker": self.marker,
            "modules": list(self.modules) or None,
            "target_role": self.target_role,
            "target_kind": None if self.target_kind == "module" else self.target_kind,
            "transitive": self.transitive,
            "cases": self.cases,
        }
        return _compact(data)


@dataclass(frozen=True)
class PrincipleError:
    """A typical error. Either ``detected_by`` names the marker that fails on it
    (and ``what`` and ``signature`` are set), or ``gap`` names the known gap
    that lets it pass. ``operator`` names the mutation operator
    (``mutation.operators``) that seeds this kind of error into a task's
    reference, for ``prepare_task``; ``None`` when no operator does."""

    id: str
    title: str
    why: str
    fix: str
    detected_by: Optional[str] = None
    gap: Optional[str] = None
    what: Optional[str] = None
    signature: Optional[ErrorSignature] = None
    operator: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return _compact(
            {
                "id": self.id,
                "title": self.title,
                "detected_by": self.detected_by,
                "gap": self.gap,
                "operator": self.operator,
                "what": self.what,
                "why": self.why,
                "fix": self.fix,
                "signature": self.signature.as_dict() if self.signature else None,
            }
        )


@dataclass(frozen=True)
class NeutralChange:
    """A change unrelated to the principle: it must not count as an error."""

    id: str
    title: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title}


@dataclass(frozen=True)
class Gap:
    """Something about the principle the tool cannot check yet, and why."""

    id: str
    title: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "detail": self.detail}


@dataclass(frozen=True)
class Principle:
    """One catalogue entry."""

    id: str
    name: str
    level: str
    summary: str
    why: str
    roles: Mapping[str, str]
    checks: tuple[CheckTemplate, ...]
    errors: tuple[PrincipleError, ...]
    neutral: tuple[NeutralChange, ...]
    gaps: tuple[Gap, ...]

    @property
    def brief(self) -> str:
        """The first sentence of the summary."""
        return _SENTENCE_END.split(self.summary, maxsplit=1)[0]

    def to_dict(self) -> dict[str, Any]:
        """The entry as JSON-able data; a field an item does not set is left out."""
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "summary": self.summary,
            "why": self.why,
            "roles": dict(self.roles),
            "checks": [check.to_dict() for check in self.checks],
            "errors": [error.to_dict() for error in self.errors],
            "neutral": [item.to_dict() for item in self.neutral],
            "gaps": [gap.to_dict() for gap in self.gaps],
        }


def signature_matches(declared: Mapping[str, Any], observed: Mapping[str, Any]) -> bool:
    """A declared signature matches an observed one (``fact_signature``) when
    every key it declares has the observed value; keys it leaves out are free."""
    return all(
        key in observed and observed[key] == value for key, value in declared.items()
    )


def fact_signature(fact: Mapping[str, Any]) -> dict[str, Any]:
    """A fact of a failed result (``details.facts``) reduced to the keys of an
    ``ErrorSignature``. Not the names a submission chooses (functions, modules)
    nor those of the catalogue's own task (attributes, classes): of an
    attribute only whether it is private counts."""
    found: dict[str, Any] = {
        key: fact[key]
        for key in ("kind", "callee", "change")
        if fact.get(key) is not None
    }
    found["via"] = bool(fact.get("via"))
    if fact.get("attribute") is not None:
        found["private"] = str(fact["attribute"]).startswith("_")
    return found


class _Table:
    """Typed access to one TOML table; every problem names where it is."""

    def __init__(self, data: Any, where: str) -> None:
        if not isinstance(data, dict):
            raise CatalogError(f"{where} must be a table")
        self._data: dict[str, Any] = data
        self.where = where

    def check_keys(
        self, required: tuple[str, ...], optional: tuple[str, ...] = ()
    ) -> None:
        for key in required:
            if key not in self._data:
                raise CatalogError(f"{self.where}: missing key {key!r}")
        for key in self._data:
            if key not in required + optional:
                raise CatalogError(f"{self.where}: unknown key {key!r}")

    def text(self, key: str) -> str:
        value = self._data[key]
        if not isinstance(value, str) or not value.strip():
            raise CatalogError(f"{self.where}: {key!r} must be a string")
        return " ".join(value.split())

    def optional_text(self, key: str) -> Optional[str]:
        return self.text(key) if key in self._data else None

    def optional_bool(self, key: str) -> Optional[bool]:
        value = self._data.get(key)
        if value is not None and not isinstance(value, bool):
            raise CatalogError(f"{self.where}: {key!r} must be a boolean")
        return value

    def tables(self, key: str) -> list[_Table]:
        value = self._data.get(key, [])
        if not isinstance(value, list):
            raise CatalogError(f"{self.where}: {key!r} must be an array of tables")
        return [
            _Table(item, f"{self.where}: {key}[{index}]")
            for index, item in enumerate(value)
        ]

    def table(self, key: str) -> _Table:
        return _Table(self._data[key], f"{self.where}: {key}")

    def raw(self) -> dict[str, Any]:
        return self._data


def _signature(table: _Table) -> ErrorSignature:
    table.check_keys(("kind",), ("via", "callee", "change", "private"))
    kind = table.text("kind")
    if kind not in FACT_KINDS:
        raise CatalogError(f"{table.where}: kind {kind!r} is not one of {FACT_KINDS}")
    callee = table.optional_text("callee")
    change = table.optional_text("change")
    private = table.optional_bool("private")
    if callee is not None and kind != "call":
        raise CatalogError(f"{table.where}: 'callee' applies only to kind 'call'")
    if change is not None and kind != "write":
        raise CatalogError(f"{table.where}: 'change' applies only to kind 'write'")
    if private is not None and kind != "write":
        raise CatalogError(f"{table.where}: 'private' applies only to kind 'write'")
    if change is not None and change not in WRITE_CHANGES:
        raise CatalogError(
            f"{table.where}: change {change!r} is not one of {WRITE_CHANGES}"
        )
    if callee is not None and not _CALLEE.fullmatch(callee):
        raise CatalogError(f"{table.where}: callee {callee!r} must be 'module:name'")
    return ErrorSignature(
        kind=kind,
        via=table.optional_bool("via"),
        callee=callee,
        change=change,
        private=private,
    )


def _check_placeholders(template: str, where: str) -> None:
    try:
        fields = [
            field for _, field, _, _ in string.Formatter().parse(template) if field
        ]
    except ValueError as error:
        raise CatalogError(
            f"{where}: 'what' is not a valid template: {error}"
        ) from error
    for field in fields:
        if field not in PLACEHOLDERS:
            raise CatalogError(
                f"{where}: unknown placeholder {field!r} in 'what'; "
                f"known: {', '.join(PLACEHOLDERS)}"
            )


def _check(table: _Table, roles: Mapping[str, str]) -> CheckTemplate:
    table.check_keys(
        ("role", "marker"),
        ("cases", "modules", "target_role", "transitive", "target_kind"),
    )
    role = table.text("role")
    if role not in roles:
        raise CatalogError(f"{table.where}: role {role!r} is not one of the [roles]")
    target_role = table.optional_text("target_role")
    if target_role is not None and target_role not in roles:
        raise CatalogError(
            f"{table.where}: target_role {target_role!r} is not one of the [roles]"
        )
    target_kind = table.optional_text("target_kind") or "module"
    if target_kind not in TARGET_KINDS:
        raise CatalogError(
            f"{table.where}: target_kind {target_kind!r} is not one of {TARGET_KINDS}"
        )
    if target_kind == "class" and target_role is None:
        raise CatalogError(f"{table.where}: target_kind 'class' needs a target_role")
    marker = table.text("marker")
    if marker not in MARKERS:
        raise CatalogError(
            f"{table.where}: marker {marker!r} is not one of the tool's markers"
        )
    if target_kind == "class" and marker not in CLASS_TARGET_MARKERS:
        raise CatalogError(
            f"{table.where}: target_kind 'class' is for "
            f"{', '.join(sorted(CLASS_TARGET_MARKERS))}, not {marker!r}"
        )
    if target_kind == "class" and "modules" in table.raw():
        raise CatalogError(
            f"{table.where}: target_kind 'class' takes its one target from "
            "target_role: remove 'modules'"
        )
    static = marker in STATIC_MARKERS
    if static == ("cases" in table.raw()):
        raise CatalogError(
            f"{table.where}: "
            + (
                f"{marker!r} is static and runs no cases: remove 'cases'"
                if static
                else "missing key 'cases'"
            )
        )
    modules = table.raw().get("modules", [])
    if not isinstance(modules, list) or not all(isinstance(m, str) for m in modules):
        raise CatalogError(f"{table.where}: 'modules' must be a list of strings")
    for module in modules:
        if not _DOTTED_NAME.fullmatch(module):
            raise CatalogError(
                f"{table.where}: module {module!r} must be a dotted name"
            )
    return CheckTemplate(
        role=role,
        marker=marker,
        cases=table.optional_text("cases"),
        modules=tuple(modules),
        target_role=target_role,
        transitive=table.optional_bool("transitive"),
        target_kind=target_kind,
    )


def _error(table: _Table, markers: set[str], gap_ids: set[str]) -> PrincipleError:
    raw = table.raw()
    if ("detected_by" in raw) == ("gap" in raw):
        raise CatalogError(f"{table.where}: needs either 'detected_by' or 'gap'")
    common = ("id", "title", "why", "fix")
    if "gap" in raw:
        table.check_keys(common + ("gap",))
        gap = table.text("gap")
        if gap not in gap_ids:
            raise CatalogError(f"{table.where}: gap {gap!r} is not one of the [[gaps]]")
        return PrincipleError(
            id=table.text("id"),
            title=table.text("title"),
            why=table.text("why"),
            fix=table.text("fix"),
            gap=gap,
        )
    table.check_keys(common + ("detected_by", "what", "signature"), ("operator",))
    operator = table.optional_text("operator")
    if operator is not None and operator not in OPERATORS:
        raise CatalogError(
            f"{table.where}: operator {operator!r} is not one of {', '.join(OPERATORS)}"
        )
    detected_by = table.text("detected_by")
    if detected_by not in markers:
        raise CatalogError(
            f"{table.where}: {detected_by!r} is not the marker of any check"
        )
    what = table.text("what")
    _check_placeholders(what, table.where)
    signature = _signature(table.table("signature"))
    if MARKER_FACT_KINDS.get(detected_by) != signature.kind:
        raise CatalogError(
            f"{table.where}: {detected_by!r} never reports kind {signature.kind!r}"
        )
    return PrincipleError(
        id=table.text("id"),
        title=table.text("title"),
        why=table.text("why"),
        fix=table.text("fix"),
        detected_by=detected_by,
        what=what,
        signature=signature,
        operator=operator,
    )


def _unambiguous(entry: _Table, errors: tuple[PrincipleError, ...]) -> None:
    """No two errors of one marker declare the same signature."""
    seen: dict[tuple[Optional[str], ErrorSignature], str] = {}
    for error in errors:
        if error.signature is None:
            continue
        key = (error.detected_by, error.signature)
        if key in seen:
            raise CatalogError(
                f"{entry.where}: error {error.id!r} has the signature of "
                f"{seen[key]!r}; the two cannot be told apart"
            )
        seen[key] = error.id


# Error ids the tool gives on its own, for every principle (``classify``):
# no catalogue error may take one.
RESERVED_ERROR_IDS = ("missing_required_entity", "syntax_error", "unclassified")


def _not_reserved(entry: _Table, errors: tuple[PrincipleError, ...]) -> None:
    for error in errors:
        if error.id in RESERVED_ERROR_IDS:
            raise CatalogError(
                f"{entry.where}: error id {error.id!r} is reserved for the tool"
            )


def _unique_ids(entry: _Table, ids: list[str]) -> None:
    seen: set[str] = set()
    for item_id in ids:
        if item_id in seen:
            raise CatalogError(f"{entry.where}: duplicate id {item_id!r}")
        seen.add(item_id)


def parse_principle(data: Mapping[str, Any], where: str) -> Principle:
    """Validate one entry's TOML data; ``where`` names it in every error."""
    entry = _Table(dict(data), where)
    entry.check_keys(
        ("id", "name", "level", "summary", "why", "roles", "checks", "errors"),
        ("neutral", "gaps"),
    )
    roles_table = entry.table("roles")
    roles = {role: roles_table.text(role) for role in roles_table.raw()}
    if not roles:
        raise CatalogError(f"{where}: [roles] is empty")
    checks = tuple(_check(table, roles) for table in entry.tables("checks"))
    gaps = []
    for table in entry.tables("gaps"):
        table.check_keys(("id", "title", "detail"))
        gaps.append(Gap(table.text("id"), table.text("title"), table.text("detail")))
    markers = {check.marker for check in checks}
    gap_ids = {gap.id for gap in gaps}
    errors = tuple(_error(table, markers, gap_ids) for table in entry.tables("errors"))
    neutral = []
    for table in entry.tables("neutral"):
        table.check_keys(("id", "title"))
        neutral.append(NeutralChange(table.text("id"), table.text("title")))
    _unique_ids(entry, [e.id for e in errors] + [n.id for n in neutral])
    _not_reserved(entry, errors)
    _unambiguous(entry, errors)
    _unique_ids(entry, [g.id for g in gaps])
    return Principle(
        id=entry.text("id"),
        name=entry.text("name"),
        level=entry.text("level"),
        summary=entry.text("summary"),
        why=entry.text("why"),
        roles=MappingProxyType(roles),
        checks=checks,
        errors=errors,
        neutral=tuple(neutral),
        gaps=tuple(gaps),
    )


@lru_cache(maxsize=8)
def _load(directory: Path) -> Mapping[str, Principle]:
    catalogue: dict[str, Principle] = {}
    for path in sorted(directory.glob("*.toml")):
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            raise CatalogError(f"{path}: not valid TOML: {error}") from error
        principle = parse_principle(data, str(path))
        if principle.id != path.stem:
            raise CatalogError(
                f"{path}: the file must be named after its id {principle.id!r}"
            )
        catalogue[principle.id] = principle
    return MappingProxyType(catalogue)


def load_catalog(directory: Optional[Path] = None) -> dict[str, Principle]:
    """Every principle of the catalogue by id (the packaged one by default)."""
    return dict(_load(Path(directory or CATALOG_DIR).resolve()))


def get_principle(principle_id: str) -> Principle:
    """One principle of the packaged catalogue; ``UnknownPrincipleError`` if none."""
    catalogue = load_catalog()
    if principle_id not in catalogue:
        raise UnknownPrincipleError(principle_id, sorted(catalogue))
    return catalogue[principle_id]
