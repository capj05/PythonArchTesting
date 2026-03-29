from __future__ import annotations

from typing import Any, List, Tuple

from src.config import Config
from src.entities import Entity


def compile_rules(
    source_entities: List[Entity],
    cfg: Config,
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compatibility shim to canonical ``src.rules.compilation`` orchestrator."""
    from src.rules.compilation.orchestrator import compile_rules as _compile_rules

    return _compile_rules(source_entities, cfg)


__all__ = ["compile_rules"]
