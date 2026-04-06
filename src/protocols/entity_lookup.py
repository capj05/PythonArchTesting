from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Sequence

from src.entities import Entity


@dataclass
class ProtocolEntityLookup:
    entities: Sequence[Entity]
    _module_entities: dict[str, Entity] = field(init=False, repr=False)
    _classes_by_fqn: dict[str, tuple[Entity, ...]] = field(init=False, repr=False)
    _classes_by_name: dict[str, tuple[Entity, ...]] = field(init=False, repr=False)
    _alias_cache: dict[str, dict[str, str]] = field(default_factory=dict, repr=False)
    _resolved_bases_cache: dict[str, tuple[Entity, ...]] = field(
        default_factory=dict, repr=False
    )

    def __post_init__(self) -> None:
        module_entities: dict[str, Entity] = {}
        classes_by_fqn: dict[str, list[Entity]] = {}
        classes_by_name: dict[str, list[Entity]] = {}

        for entity in self.entities:
            if entity.kind == "module":
                module_entities.setdefault(entity.module_path, entity)
            if entity.kind != "class":
                continue
            fqn = f"{entity.module_path}.{entity.name}"
            classes_by_fqn.setdefault(fqn, []).append(entity)
            classes_by_name.setdefault(entity.name, []).append(entity)

        self._module_entities = module_entities
        self._classes_by_fqn = {
            key: tuple(value) for key, value in classes_by_fqn.items()
        }
        self._classes_by_name = {
            key: tuple(value) for key, value in classes_by_name.items()
        }

    @classmethod
    def from_entities(cls, entities: Sequence[Entity]) -> ProtocolEntityLookup:
        return cls(entities)

    def module_entity(self, module_path: str) -> Entity | None:
        return self._module_entities.get(module_path)

    def import_aliases(self, module_path: str) -> dict[str, str]:
        cached = self._alias_cache.get(module_path)
        if cached is not None:
            return cached

        module_entity = self.module_entity(module_path)
        module_node = module_entity.extras.get("ast_node") if module_entity else None
        if not isinstance(module_node, ast.Module):
            empty_aliases: dict[str, str] = {}
            self._alias_cache[module_path] = empty_aliases
            return empty_aliases

        aliases: dict[str, str] = {}
        for stmt in module_node.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    local_name = alias.asname or alias.name.split(".", 1)[0]
                    target_name = (
                        alias.name if alias.asname else alias.name.split(".", 1)[0]
                    )
                    aliases[local_name] = target_name
            elif isinstance(stmt, ast.ImportFrom) and stmt.module:
                for alias in stmt.names:
                    if alias.name == "*":
                        continue
                    aliases[alias.asname or alias.name] = f"{stmt.module}.{alias.name}"

        self._alias_cache[module_path] = aliases
        return aliases

    def class_matches_by_fqn(self, qualified_name: str) -> tuple[Entity, ...]:
        return self._classes_by_fqn.get(qualified_name, ())

    def unique_class_by_fqn(self, qualified_name: str) -> Entity | None:
        matches = self.class_matches_by_fqn(qualified_name)
        if len(matches) != 1:
            return None
        return matches[0]

    def class_by_name(self, name: str) -> Entity | None:
        matches = self._classes_by_name.get(name, ())
        return matches[0] if matches else None

    def resolved_bases(self, entity: Entity) -> tuple[Entity, ...]:
        cached = self._resolved_bases_cache.get(entity.canonical_id)
        if cached is not None:
            return cached

        resolved: list[Entity] = []
        for base_ref in entity.extras.get("bases") or []:
            base_entity = self.unique_class_by_fqn(str(base_ref))
            if base_entity is not None:
                resolved.append(base_entity)

        result = tuple(resolved)
        self._resolved_bases_cache[entity.canonical_id] = result
        return result


__all__ = ["ProtocolEntityLookup"]
