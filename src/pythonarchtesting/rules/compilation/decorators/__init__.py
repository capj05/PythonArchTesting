"""Canonical decorator compilers for entity-scoped rules."""

from .api_signature import compile_required_entity_signature, compile_required_method
from .attributes import compile_required_attribute
from .constructors import compile_required_constructor
from .enum_type import compile_is_enum
from .factories import compile_required_factory
from .flow import compile_enforce_flow
from .import_policy import compile_forbid_imports
from .member_absence import compile_does_not_have
from .method_set import compile_require_method_set
from .nominal_type import (
    compile_exact_type,
    compile_inherits_directly_from,
    compile_not_subclass_of,
    compile_subclass_of,
)
from .protocols import compile_implements_protocol
from .python_modifiers import (
    compile_is_abstract_class,
    compile_is_concrete_class,
    compile_is_final_class,
)

__all__ = [
    "compile_does_not_have",
    "compile_require_method_set",
    "compile_required_attribute",
    "compile_required_constructor",
    "compile_is_enum",
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
    "compile_is_abstract_class",
    "compile_is_concrete_class",
    "compile_is_final_class",
]
