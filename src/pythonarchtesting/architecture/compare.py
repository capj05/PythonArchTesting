"""Compare a target's module graph with the one its reference implies.

The reference is the model of the intended architecture: its imports, the
calls between its modules, the objects its modules create and the libraries
it uses. The target is judged edge by edge, in reflexion-model terms: an
edge both have *converges*, an edge only the target has *diverges*, an edge
only the reference has is *absent*. What the policy neither allows nor
forbids is *undecided*: reported for a person to judge, never a failure.

Policies:

- ``strict``: every edge the reference lacks diverges;
- ``allow_new_modules``: a module the reference does not have (a helper of
  the target's own) counts as part of the modules that use it;
- ``layered``: as ``allow_new_modules``, but an extra edge diverges only
  when it points against the reference's direction (the reference reaches
  its origin from its end); any other extra edge is undecided.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pythonarchtesting.execution.module_structure import Edge

POLICIES = ("allow_new_modules", "strict", "layered")

# Language support rather than technology: using these is never a design
# decision a teacher wants to see flagged.
DEFAULT_IGNORE_EXTERNAL: tuple[str, ...] = (
    "__future__",
    "typing",
    "typing_extensions",
    "abc",
    "dataclasses",
    "enum",
    "functools",
    "itertools",
    "collections",
    "contextlib",
    "types",
    "operator",
)

T = TypeVar("T")


def parse_edge(text: str) -> Edge:
    """``"a -> b"`` as ``("a", "b")``; anything else raises ``ValueError``."""
    parts = [part.strip() for part in str(text).split("->")]
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"expected 'module -> module', got {text!r}")
    return parts[0], parts[1]


def _within(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(f"{prefix}.")


def _covered(pair: Edge, exceptions: Collection[Edge]) -> bool:
    """Whether an exception covers ``pair``; a package covers its submodules."""
    return any(
        _within(pair[0], origin) and _within(pair[1], end) for origin, end in exceptions
    )


def forbidden(pair: Edge, forbid: Collection[Edge]) -> bool:
    """Whether a ``forbid`` exception covers ``pair`` (a package covers its submodules)."""
    return _covered(pair, forbid)


def format_edge(edge: Edge) -> str:
    return f"{edge[0]} -> {edge[1]}"


@dataclass(frozen=True)
class EdgeDiff:
    """One layer of the model compared: each list sorted, edge by edge."""

    convergent: list[Edge] = field(default_factory=list)
    divergent: list[Edge] = field(default_factory=list)
    absent: list[Edge] = field(default_factory=list)
    undecided: list[Edge] = field(default_factory=list)
    allowed: list[Edge] = field(default_factory=list)
    # Every edge of the reference: an exception or ``forbid`` can put one of
    # them among ``allowed`` or ``divergent``, so ``convergent`` + ``absent``
    # alone may miss some. ``None`` where the reference is no edge set.
    reference: list[Edge] | None = None

    def to_dict(self) -> dict[str, list[str]]:
        names = ["convergent", "divergent", "absent", "undecided", "allowed"]
        if self.reference is not None:
            names.append("reference")
        return {
            name: [format_edge(edge) for edge in sorted(getattr(self, name))]
            for name in names
        }


def _reachable(start: str, edges: Iterable[Edge]) -> set[str]:
    following: dict[str, set[str]] = {}
    for origin, end in edges:
        following.setdefault(origin, set()).add(end)
    seen = {start}
    stack = [start]
    while stack:
        for nxt in following.get(stack.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def fold_new_modules(
    edges: Mapping[Edge, T], known: set[str]
) -> tuple[dict[Edge, T], dict[Edge, T]]:
    """``edges`` with every module outside ``known`` folded into its users.

    A module the reference does not have is treated as part of each module
    that uses it: its edges become theirs, and the edges into it disappear.
    A chain of new modules folds step by step. A new module no known module
    reaches has no user to fold into; its edges come back separately, as the
    second mapping.
    """
    reached: set[str] = set()
    for module in {origin for origin, _ in edges} & known:
        reached |= _reachable(module, edges)
    dropped = {
        pair: value
        for pair, value in edges.items()
        if pair[0] not in known and pair[0] not in reached
    }
    current: dict[Edge, T] = {
        pair: value for pair, value in edges.items() if pair not in dropped
    }
    for _ in range(len(current) + 1):
        new = sorted({module for pair in current for module in pair} - known)
        if not new:
            break
        module = new[0]
        users = {origin for origin, end in current if end == module}
        users.discard(module)
        folded: dict[Edge, T] = {}
        for (origin, end), value in current.items():
            if end == module:
                continue
            for start in users if origin == module else (origin,):
                if start != end:
                    folded.setdefault((start, end), value)
        current = folded
    return current, dropped


def _sorted(edges: Iterable[Edge]) -> list[Edge]:
    return sorted(set(edges))


def compare_edges(
    reference: Collection[Edge],
    target: Mapping[Edge, Any],
    *,
    policy: str,
    known: set[str],
    allow: Collection[Edge] = (),
    forbid: Collection[Edge] = (),
    permitted: Collection[Edge] = (),
) -> EdgeDiff:
    """Compare the target's module edges with the reference's under ``policy``.

    ``target`` is named by the reference's modules already; ``known`` are the
    reference's modules, so any other module is one the target added.
    ``permitted`` are further edges of the reference that the target may have
    but need not (at run time: the reference's imports its cases never
    exercised); they are convergent, never absent.
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}; expected one of {POLICIES}")
    expected = set(reference)
    undecided: list[Edge] = []
    if policy == "strict":
        edges = dict(target)
    else:
        edges, dropped = fold_new_modules(target, known)
        undecided.extend(dropped)
    convergent: list[Edge] = []
    divergent: list[Edge] = []
    allowed: list[Edge] = []
    allow_set, forbid_set = set(allow), set(forbid)
    accepted = expected | set(permitted)
    for pair in edges:
        if _covered(pair, forbid_set):
            divergent.append(pair)
        elif _covered(pair, allow_set):
            allowed.append(pair)
        elif pair in accepted:
            convergent.append(pair)
        elif policy == "layered" and pair[0] not in _reachable(pair[1], accepted):
            undecided.append(pair)
        else:
            divergent.append(pair)
    return EdgeDiff(
        convergent=_sorted(convergent),
        divergent=_sorted(divergent),
        absent=_sorted(expected - set(edges)),
        undecided=_sorted(undecided),
        allowed=_sorted(allowed),
        reference=_sorted(expected),
    )


def class_module(name: str, modules: Collection[str] = ()) -> str:
    """The module of ``"module.Qual.Name"``.

    The class part is a qualified name and may hold dots itself (a nested
    class), so the longest of ``modules`` that prefixes the name wins; without
    one, everything before the last dot is the module.
    """
    found = [m for m in modules if m and name.startswith(f"{m}.")]
    if found:
        return max(found, key=len)
    return name.rpartition(".")[0]


def compare_instances(
    reference: Collection[Edge],
    target: Mapping[Edge, Any],
    *,
    policy: str,
    reference_calls: Collection[Edge],
    allow: Collection[Edge] = (),
    forbid: Collection[Edge] = (),
    modules: Collection[str] = (),
) -> EdgeDiff:
    """Compare who creates which objects: ``(module, "module.Class")`` edges.

    Both sides are named by the reference already, and a creator the
    reference lacks has been folded into its callers. An exception names
    either the class (``"service -> repository.Repo"``) or its module
    (``"service -> repository"``). Under ``layered`` an extra edge diverges
    only when the reference's calls reach the creator from the class's
    module (the object is made "upwards"); otherwise it is undecided.
    ``modules`` are the program's modules, to tell a nested class's module.
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}; expected one of {POLICIES}")
    expected = set(reference)
    allow_set, forbid_set = set(allow), set(forbid)
    convergent: list[Edge] = []
    divergent: list[Edge] = []
    allowed: list[Edge] = []
    undecided: list[Edge] = []
    for pair in target:
        by_module = (pair[0], class_module(pair[1], modules))
        if pair in forbid_set or _covered(by_module, forbid_set):
            divergent.append(pair)
        elif pair in allow_set or _covered(by_module, allow_set):
            allowed.append(pair)
        elif pair in expected:
            convergent.append(pair)
        elif policy == "layered" and pair[0] not in _reachable(
            by_module[1], reference_calls
        ):
            undecided.append(pair)
        else:
            divergent.append(pair)
    return EdgeDiff(
        convergent=_sorted(convergent),
        divergent=_sorted(divergent),
        absent=_sorted(expected - set(target)),
        undecided=_sorted(undecided),
        allowed=_sorted(allowed),
        reference=_sorted(expected),
    )


def compare_packages(
    reference: Collection[str],
    target: Mapping[Edge, Any],
    *,
    ignore: Collection[str],
    allow: Collection[Edge] = (),
    forbid: Collection[Edge] = (),
) -> EdgeDiff:
    """Compare the libraries the target uses with the reference's.

    ``target`` maps ``(module, package)`` edges. A package the reference uses
    anywhere may be used by any module: moving ``json`` from one module to
    another is not a change of technology.
    """
    used = set(reference)
    ignored = set(ignore)
    allow_set, forbid_set = set(allow), set(forbid)
    convergent: list[Edge] = []
    divergent: list[Edge] = []
    allowed: list[Edge] = []
    for pair in target:
        if _covered(pair, forbid_set):
            # A forbidden library is a violation even if it is otherwise ignored.
            divergent.append(pair)
        elif pair[1] in ignored:
            continue
        elif _covered(pair, allow_set):
            allowed.append(pair)
        elif pair[1] in used:
            convergent.append(pair)
        else:
            divergent.append(pair)
    return EdgeDiff(
        convergent=_sorted(convergent),
        divergent=_sorted(divergent),
        allowed=_sorted(allowed),
    )


__all__ = [
    "DEFAULT_IGNORE_EXTERNAL",
    "POLICIES",
    "EdgeDiff",
    "class_module",
    "compare_edges",
    "compare_instances",
    "compare_packages",
    "fold_new_modules",
    "format_edge",
    "parse_edge",
]
