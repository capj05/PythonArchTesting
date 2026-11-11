"""Canonical orchestration for rule compilation."""

from __future__ import annotations

from typing import Any, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.entities import Entity


def compile_rules(
    source_entities: List[Entity],
    cfg: Config,
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compile entity-scoped rules from annotation declarations."""
    from pythonarchtesting.rules.compilation.declarations import (
        compile_declarations,
        in_rule_order,
    )
    from pythonarchtesting.rules.compilation.decorators.api_signature import (
        compile_required_entity_signature,
        compile_required_method,
    )
    from pythonarchtesting.rules.compilation.decorators.attributes import (
        compile_required_attribute,
    )
    from pythonarchtesting.rules.compilation.decorators.enum_type import compile_is_enum
    from pythonarchtesting.rules.compilation.decorators.flow import compile_enforce_flow
    from pythonarchtesting.rules.compilation.decorators.import_policy import (
        compile_forbid_imports,
    )
    from pythonarchtesting.rules.compilation.decorators.protocols import (
        compile_implements_protocol,
    )

    declaration_compilers: dict[str, Any] = {
        "required_entity_signature": compile_required_entity_signature,
        "required_method": compile_required_method,
        "required_attribute": compile_required_attribute,
        "is_enum": compile_is_enum,
        "enforce_flow": compile_enforce_flow,
        "forbid_imports": compile_forbid_imports,
        "implements_protocol": compile_implements_protocol,
    }

    return in_rule_order(
        *compile_declarations(
            source_entities,
            cfg,
            declaration_compilers,
            frozenset({"implements_protocol"}),
        )
    )


__all__ = ["compile_rules"]
