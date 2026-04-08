"""Compatibility facade for the canonical `pythonarchtesting.rules.compilation.common`."""

from pythonarchtesting.rules.compilation.common import (
    canonicalize_payload,
    evidence_id,
    with_rule_id_suffix,
)

__all__ = ["canonicalize_payload", "evidence_id", "with_rule_id_suffix"]
