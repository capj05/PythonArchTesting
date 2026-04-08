from __future__ import annotations

from typing import Any, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.entities import Entity


def compile_rules(
    source_entities: List[Entity],
    cfg: Config,
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compatibility shim to canonical ``pythonarchtesting.rules.compilation`` orchestrator."""
    from pythonarchtesting.rules.compilation.orchestrator import (
        compile_rules as _compile_rules,
    )

    return _compile_rules(source_entities, cfg)


__all__ = ["compile_rules"]
