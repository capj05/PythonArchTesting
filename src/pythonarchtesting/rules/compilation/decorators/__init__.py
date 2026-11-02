"""Canonical decorator compilers for entity-scoped rules."""

from .api_signature import compile_required_entity_signature, compile_required_method
from .architecture import compile_architecture_entry
from .attributes import compile_required_attribute
from .constructors import compile_required_constructor
from .enum_type import compile_is_enum
from .factories import compile_required_factory
from .flow import compile_enforce_flow
from .import_policy import compile_forbid_imports
from .member_absence import compile_does_not_have
from .member_set import compile_require_member_set
from .method_set import compile_require_method_set
from .module_interface import compile_module_interface
from .module_structure import compile_enforce_layers, compile_forbid_cycles
from .nominal_type import (
    compile_exact_type,
    compile_inherits_directly_from,
    compile_not_subclass_of,
    compile_subclass_of,
)
from .protocols import compile_implements_protocol
from .python_modifiers import (
    compile_is_abstract_class,
    compile_is_abstract_method,
    compile_is_concrete_class,
    compile_is_final_class,
    compile_is_final_method,
    compile_is_non_abstract_method,
    compile_is_non_final_class,
    compile_is_non_final_method,
)
from .runtime_structure import (
    compile_enforce_reference_calls,
    compile_enforce_runtime_observer,
    compile_forbid_foreign_writes,
    compile_forbid_runtime_calls,
    compile_forbid_runtime_imports,
    compile_forbid_runtime_instantiation,
    compile_forbid_runtime_members,
    compile_implements_runtime_protocol,
    compile_is_runtime_abstract_class,
    compile_is_runtime_concrete_class,
    compile_is_runtime_singleton,
    compile_require_runtime_calls,
    compile_require_runtime_delegation,
    compile_require_runtime_members,
)

__all__ = [
    "compile_enforce_layers",
    "compile_forbid_cycles",
    "compile_architecture_entry",
    "compile_module_interface",
    "compile_does_not_have",
    "compile_forbid_foreign_writes",
    "compile_forbid_runtime_calls",
    "compile_enforce_reference_calls",
    "compile_enforce_runtime_observer",
    "compile_is_runtime_singleton",
    "compile_require_runtime_delegation",
    "compile_forbid_runtime_members",
    "compile_implements_runtime_protocol",
    "compile_is_runtime_abstract_class",
    "compile_is_runtime_concrete_class",
    "compile_require_runtime_members",
    "compile_forbid_runtime_imports",
    "compile_forbid_runtime_instantiation",
    "compile_require_runtime_calls",
    "compile_require_member_set",
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
    "compile_is_abstract_method",
    "compile_is_concrete_class",
    "compile_is_final_class",
    "compile_is_final_method",
    "compile_is_non_abstract_method",
    "compile_is_non_final_class",
    "compile_is_non_final_method",
]
