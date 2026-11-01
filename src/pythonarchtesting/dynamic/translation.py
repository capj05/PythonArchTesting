"""Translate names between the reference and a target for the runtime rules.

A runtime marker is written against the reference: it names reference modules
(``forbid_runtime_calls("repository")``) and reference classes
(``{"$new": "repository.OrderRepository"}``). A target may keep the same
entities in modules of other names, or merge several modules into one. The
matching step pairs the reference's entities with the target's, and the
names follow those pairs:

- what the probe observed in the target (a call into ``storage``) is named by
  the reference module of the entity it hit (``repository``), so a renamed
  module neither hides a violation nor creates one;
- a name sent to the probe (a ``$new`` class, a module whose import is
  forbidden) is replaced by the target's name for the same entity.

Names of modules outside the project, and of entities the matching step did
not pair, are kept as written.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def _in_module(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _majority(votes: dict[str, Counter[str]]) -> dict[str, str]:
    """The most frequent value per key; on a tie the key itself, if tied."""
    chosen: dict[str, str] = {}
    for key, counter in votes.items():
        top = max(counter.values())
        tied = sorted(name for name, count in counter.items() if count == top)
        chosen[key] = key if key in tied else tied[0]
    return chosen


class NameTranslation:
    """Pairs of reference and target names taken from the matching step."""

    def __init__(self, pairs: list[tuple[Any, Any]]) -> None:
        self._by_source: dict[tuple[str, str], Any] = {}
        self._by_target: dict[tuple[str, str], Any] = {}
        forward: dict[str, Counter[str]] = {}
        backward: dict[str, Counter[str]] = {}
        for source, target in pairs:
            self._by_source[(source.module_path, source.qualname)] = target
            self._by_target[(target.module_path, target.qualname)] = source
            forward.setdefault(source.module_path, Counter())[target.module_path] += 1
            backward.setdefault(target.module_path, Counter())[source.module_path] += 1
        self._to_target = _majority(forward)
        self._to_source = _majority(backward)
        images = Counter(self._to_target.values())
        # A target module standing for several reference modules cannot stand
        # in for any one of them in a name sent to the probe.
        self._merged = {module for module, count in images.items() if count > 1}

    @classmethod
    def from_context(cls, ctx: Any) -> "NameTranslation":
        from pythonarchtesting.matching import MatchStatus

        # A low-confidence match (typically an entity moved to a renamed
        # module) still names the target's best candidate, which beats a
        # reference name the target does not have at all.
        usable = (MatchStatus.MATCHED, MatchStatus.LOW_CONFIDENCE)
        source_by_id = getattr(ctx, "source_by_id", None) or {}
        target_by_id = getattr(ctx, "target_by_id", None) or {}
        matches = getattr(ctx, "matches", None) or {}
        # A target a match took is not a low-confidence guess's to name.
        taken = {
            getattr(match, "target_id", None)
            for match in matches.values()
            if getattr(match, "status", None) == MatchStatus.MATCHED
        }
        pairs = []
        for source_id, match in matches.items():
            status = getattr(match, "status", None)
            if status not in usable:
                continue
            if status != MatchStatus.MATCHED and match.target_id in taken:
                continue
            source = source_by_id.get(source_id)
            target = target_by_id.get(getattr(match, "target_id", None))
            if all(
                hasattr(entity, "module_path") and hasattr(entity, "qualname")
                for entity in (source, target)
            ):
                pairs.append((source, target))
        return cls(pairs)

    def source_module(self, module: str, qualname: str) -> str:
        """The reference module of code the target ran in ``module``.

        The entity itself decides when it was matched; a nested function or
        a method the reference lacks is decided by the nearest enclosing
        entity that was, and otherwise by the module the target's matched
        entities of ``module`` mostly come from.
        """
        found = self.entity_module(module, qualname)
        if found is not None:
            return found
        return self._to_source.get(module, module)

    def target_name(self, module: str, qualname: str) -> tuple[str, str] | None:
        """The target ``(module, qualname)`` the reference's entity was matched to."""
        target = self._by_source.get((module, qualname))
        if target is None:
            return None
        return str(target.module_path), str(target.qualname)

    def source_name(self, module: str, qualname: str) -> tuple[str, str] | None:
        """The reference ``(module, qualname)`` the target's entity was matched to."""
        source = self._by_target.get((module, qualname))
        if source is None:
            return None
        return str(source.module_path), str(source.qualname)

    def entity_module(self, module: str, qualname: str) -> str | None:
        """The reference module of the nearest matched entity enclosing the code."""
        parts = str(qualname).split(".")
        for end in range(len(parts), 0, -1):
            source = self._by_target.get((module, ".".join(parts[:end])))
            if source is not None:
                return str(source.module_path)
        return None

    def target_modules(self, name: str) -> list[str]:
        """Target modules standing for the reference module or package ``name``."""
        names: set[str] = set()
        for module, image in self._to_target.items():
            if _in_module(module, name) and image not in self._merged:
                names.add(image)
        if name not in self._to_target or self._to_target[name] in self._merged:
            names.add(name)
        return sorted(names)

    def _new_name(self, name: str, source: Any, target: Any) -> str:
        head, _, rest = name.partition(".")
        entity = None
        if rest:
            entity = self._by_source.get((head, rest))
        if entity is None:
            entity = self._by_source.get((source.module_path, name))
        if entity is None:
            return name
        if entity.module_path == target.module_path:
            return str(entity.qualname)
        return f"{entity.module_path}.{entity.qualname}"

    def value(self, value: Any, source: Any, target: Any) -> Any:
        """``value`` of a case with every ``$new`` naming the target's class."""
        if isinstance(value, list):
            return [self.value(item, source, target) for item in value]
        if not isinstance(value, dict):
            return value
        translated = {
            key: self.value(item, source, target) for key, item in value.items()
        }
        if isinstance(value.get("$new"), str):
            translated["$new"] = self._new_name(value["$new"], source, target)
        return translated

    def _step_name(self, name: str, source: Any) -> str:
        """The target's name for method ``name`` of the instance ``source`` uses."""
        owner = (
            source.qualname
            if getattr(source, "kind", None) == "class"
            else str(source.qualname).rpartition(".")[0]
        )
        entity = self._by_source.get((source.module_path, f"{owner}.{name}"))
        return str(entity.qualname).rpartition(".")[2] if entity is not None else name

    def _member_name(self, name: str, source: Any) -> str:
        """The target's name for method ``name`` of class ``source``, or of a
        function of its module (a singleton accessor such as ``get_config``)."""
        translated = self._step_name(name, source)
        if translated != name:
            return translated
        entity = self._by_source.get((source.module_path, name))
        return str(entity.qualname) if entity is not None else name

    def observation(
        self, observe: dict[str, Any], source: Any, target: Any = None
    ) -> dict[str, Any]:
        """``observe`` with the members a pattern rule calls, and the classes a
        member must hold (``types``, given ``target``), named as the target's."""
        translated = dict(observe)
        if target is not None and isinstance(observe.get("types"), dict):
            translated["types"] = {
                member: self._new_name(str(name), source, target)
                for member, name in observe["types"].items()
            }
        if isinstance(observe.get("observer"), dict):
            spec = dict(observe["observer"])
            for key in ("subscribe", "notify", "unsubscribe"):
                if isinstance(spec.get(key), str):
                    spec[key] = self._member_name(spec[key], source)
            translated["observer"] = spec
        singleton = observe.get("singleton")
        if isinstance(singleton, dict) and isinstance(singleton.get("access"), str):
            translated["singleton"] = {
                **singleton,
                "access": self._member_name(singleton["access"], source),
            }
        return translated

    def cases(
        self, cases: list[dict[str, Any]], source: Any, target: Any
    ) -> list[dict[str, Any]]:
        translated = [self.value(case, source, target) for case in cases]
        for case in translated:
            for step in case.get("steps") or []:
                if isinstance(step, dict) and isinstance(step.get("call"), str):
                    step["call"] = self._step_name(step["call"], source)
        return translated


__all__ = ["NameTranslation"]
