"""Canonical compilation entrypoints for supported annotation rules."""

from .common import canonicalize_payload, evidence_id, with_rule_id_suffix
from .decorators import (
    compile_enforce_flow,
    compile_forbid_imports,
    compile_implements_protocol,
    compile_required_entity_signature,
    compile_required_method,
)
from .orchestrator import compile_rules

__all__ = [
    "canonicalize_payload",
    "evidence_id",
    "with_rule_id_suffix",
    "compile_required_entity_signature",
    "compile_required_method",
    "compile_enforce_flow",
    "compile_forbid_imports",
    "compile_implements_protocol",
    "compile_rules",
]
