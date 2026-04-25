"""Canonical decorator compilers for entity-scoped rules."""

from .api_signature import compile_required_entity_signature, compile_required_method
from .attributes import compile_required_attribute
from .constructors import compile_required_constructor
from .factories import compile_required_factory
from .flow import compile_enforce_flow
from .import_policy import compile_forbid_imports
from .member_absence import compile_does_not_have
from .nominal_type import (
    compile_exact_type,
    compile_inherits_directly_from,
    compile_not_subclass_of,
    compile_subclass_of,
)
from .protocols import compile_implements_protocol

__all__ = [
    "compile_does_not_have",
    "compile_required_attribute",
    "compile_required_constructor",
    "compile_required_factory",
    "compile_required_entity_signature",
    "compile_required_method",
    "compile_enforce_flow",
    "compile_forbid_imports",
    "compile_implements_protocol",
    "compile_exact_type",
    "compile_inherits_directly_from",
    "compile_not_subclass_of",
    "compile_subclass_of",
]
