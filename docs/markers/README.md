# Per-Marker Reference

One focused page per marker. Each page covers placement, a minimal example,
what the rule checks, and what it does not check. For the full option surface
see [../api-reference.md](../api-reference.md). For ready-made combinations see
[../pattern-recipes.md](../pattern-recipes.md).

All markers are imported from `pythonarchtesting.rules`.

## Signature And Shape

- [required_entity_signature](required_entity_signature.md) — function or method signature contract
- [required_method](required_method.md) — required method on a class with a compatible signature
- [require_method_set](require_method_set.md) — a set of required methods at class level
- [require_member_set](require_member_set.md) — a set of required members (methods, attributes, properties, descriptors, constructors)
- [required_constructor](required_constructor.md) — required `__init__` or `__new__` shape
- [required_factory](required_factory.md) — required factory classmethod, staticmethod, or constructor
- [required_attribute](required_attribute.md) — required class or instance attribute
- [does_not_have](does_not_have.md) — explicitly forbid a member by name

## Imports

- [forbid_imports](forbid_imports.md) — module-scoped or package-scoped import policy

## Type Identity And Inheritance

- [implements_protocol](implements_protocol.md) — structural protocol conformance
- [subclass_of](subclass_of.md) — require nominal subclass of a matched base
- [exact_type](exact_type.md) — require the target to be exactly the matched base
- [not_subclass_of](not_subclass_of.md) — forbid nominal subclass of a matched base
- [inherits_directly_from](inherits_directly_from.md) — require direct nominal inheritance
- [is_enum](is_enum.md) — require an `enum.Enum`-family class

## Abstractness And Finality

- [is_abstract_class](is_abstract_class.md) — class has unresolved abstract members
- [is_concrete_class](is_concrete_class.md) — class has no unresolved abstract members
- [is_final_class](is_final_class.md) — class decorated with `@final`
- [is_non_final_class](is_non_final_class.md) — class not decorated with `@final`
- [is_abstract_method](is_abstract_method.md) — method decorated with `@abstractmethod`
- [is_non_abstract_method](is_non_abstract_method.md) — method not decorated as abstract
- [is_final_method](is_final_method.md) — method decorated with `@final`
- [is_non_final_method](is_non_final_method.md) — method not decorated with `@final`

## Variable Flow

- [flow](flow.md) — mark a statement as a stage in a tracked variable flow
- [enforce_flow](enforce_flow.md) — require flow stages to appear in declared order
