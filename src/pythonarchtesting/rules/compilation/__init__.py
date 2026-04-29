"""Canonical compilation entrypoints for supported annotation rules."""

from .common import canonicalize_payload, evidence_id, with_rule_id_suffix
from .decorators import (
    compile_enforce_flow,
    compile_exact_type,
    compile_forbid_imports,
    compile_implements_protocol,
    compile_inherits_directly_from,
    compile_is_abstract_class,
    compile_is_abstract_method,
    compile_is_concrete_class,
    compile_is_enum,
    compile_is_final_class,
    compile_is_final_method,
    compile_not_subclass_of,
    compile_require_method_set,
    compile_required_entity_signature,
    compile_required_factory,
    compile_required_method,
    compile_subclass_of,
)
from .orchestrator import compile_rules

__all__ = [
    "canonicalize_payload",
    "evidence_id",
    "with_rule_id_suffix",
    "compile_required_entity_signature",
    "compile_required_factory",
    "compile_require_method_set",
    "compile_required_method",
    "compile_enforce_flow",
    "compile_forbid_imports",
    "compile_implements_protocol",
    "compile_exact_type",
    "compile_inherits_directly_from",
    "compile_is_enum",
    "compile_is_abstract_class",
    "compile_is_abstract_method",
    "compile_is_concrete_class",
    "compile_is_final_class",
    "compile_is_final_method",
    "compile_not_subclass_of",
    "compile_subclass_of",
    "compile_rules",
]
