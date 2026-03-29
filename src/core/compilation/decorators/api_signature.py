"""Compatibility facade for the canonical API-signature compilers."""

from src.rules.compilation.decorators.api_signature import (
    compile_required_entity_signature,
    compile_required_method,
)

__all__ = ["compile_required_entity_signature", "compile_required_method"]
