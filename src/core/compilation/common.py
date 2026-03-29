"""Compatibility facade for the canonical `src.rules.compilation.common`."""

from src.rules.compilation.common import (
    canonicalize_payload,
    evidence_id,
    with_rule_id_suffix,
)

__all__ = ["canonicalize_payload", "evidence_id", "with_rule_id_suffix"]
