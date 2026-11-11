# Per-Marker Reference

One focused page per marker. Each page covers placement, a minimal example,
what the rule checks, and what it does not check. For the full option surface
see [../api-reference.md](../api-reference.md). For ready-made combinations see
[../pattern-recipes.md](../pattern-recipes.md).

All markers are imported from `pythonarchtesting.rules`.

## Severity

Every marker except `flow` takes `severity`: `"error"` (the default),
`"warning"` or `"info"`, in any case; `severity=None` is the default. Any other
value (`"fatal"`, `"warn"`, `1`) makes the declaration invalid, like an invalid
value of any other argument: the marker is not compiled with a guessed
severity but dropped, with a `compiler_invalid_param` sentinel rule for the
parameter `severity` (valid values `["error", "warning", "info"]`) and compiler
evidence with the issue `invalid_severity`.

## Logical And Enumerated Arguments

The same rule holds for every logical argument (one typed `bool`:
`declared_only`, `allow_missing`, `ignore_type_checking`, `transitive`, …) and
every enumerated argument (one that takes a value from a fixed list:
`signature_mode`, `mode`, `name_match`, `storage`, `scope`, `policy`, …) of
every marker:

- A logical argument takes only `True` or `False`. Any other value (`"no"`,
  `"false"`, `1`, `0`) is not read for its truthiness but makes the
  declaration invalid: a `compiler_invalid_param` sentinel rule for the
  argument (valid values `[True, False]`) and compiler evidence with the issue
  `invalid_<argument>`, for example `invalid_declared_only`.
- An enumerated argument takes only the values its marker's page lists, in
  any case where the marker reads it so (`signature_mode="Exact"` is
  `"exact"`). Any other value makes the declaration invalid instead of being
  replaced by the default. An argument that was already checked keeps the
  report it always had (for example `forbid_imports(mode=…)` with the issue
  `invalid_mode`); the others report it as a logical argument does: a
  sentinel with the valid values and the issue `invalid_<argument>`, for
  example `required_entity_signature(mode="strict")` with `invalid_mode`.
- `None` declares the default of either kind, as if the argument were left
  out.

The sentinel and the evidence are the ones the marker reports an invalid
severity with.

## Positional Arguments

A marker whose page lists one argument as `(positional)` takes exactly that
one positional argument; every other argument is a keyword. A positional
argument beyond it — `implements_protocol(Seller, "x")`,
`required_attribute("name", 4)`, or any positional argument of a marker
without one, such as `required_method("x")` — is not used for anything: the
declaration reports it as a warning, an `arg` issue with the argument's index
and position (`--validate-declarations` shows it). Only the first argument is
the value; a literal after a first argument that cannot be read does not take
its place.

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
- [enforce_layers](enforce_layers.md) — one layer order for the whole program, on imports and (with `--dynamic`) on calls
- [forbid_cycles](forbid_cycles.md) — no dependency cycle between modules, on imports and (with `--dynamic`) on calls
- [module_interface](module_interface.md) — a module used by the others only through its listed or public names, on imports and (with `--dynamic`) on calls
- [architecture_entry](architecture_entry.md) — the reference's module dependencies as the model, on imports and (with `--dynamic`) on calls, objects created and libraries used

## Encapsulation

- [forbid_private_access](forbid_private_access.md) — private attributes of another object read from outside its class (static)

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

## Runtime Structure

Opt-in: these markers execute target code and run only with `--dynamic`. Cases
only give call arguments; results are never compared. See
[../dynamic-checks.md](../dynamic-checks.md).

- [forbid_runtime_calls](forbid_runtime_calls.md) — calls from the target's module into a layer it must not reach
- [require_runtime_calls](require_runtime_calls.md) — calls into a layer the target must delegate to
- [enforce_reference_calls](enforce_reference_calls.md) — module-to-module call graph learned from the reference
- [forbid_foreign_writes](forbid_foreign_writes.md) — attribute assignments from outside the object's class
- [forbid_runtime_instantiation](forbid_runtime_instantiation.md) — dependencies created instead of injected
- [require_runtime_members](require_runtime_members.md) — members a built instance must have, dynamic ones included
- [forbid_runtime_members](forbid_runtime_members.md) — members a built instance must not have
- [is_runtime_concrete_class](is_runtime_concrete_class.md) — instantiable as Python decides, external abstract bases included
- [is_runtime_abstract_class](is_runtime_abstract_class.md) — abstract as Python decides
- [implements_runtime_protocol](implements_runtime_protocol.md) — protocol conformance of a built instance
- [is_runtime_singleton](is_runtime_singleton.md) — Singleton: one shared instance
- [enforce_runtime_observer](enforce_runtime_observer.md) — Observer: listeners notified, and not after unsubscribing
- [require_runtime_delegation](require_runtime_delegation.md) — Strategy/Decorator/Proxy: work delegated to an injected collaborator
- [forbid_runtime_imports](forbid_runtime_imports.md) — modules a target module actually imports when it is loaded
- [enforce_flow with `cases`](enforce_flow.md#runtime-check-with-cases) — processing stages run in the reference's order, told apart by the project functions each calls
