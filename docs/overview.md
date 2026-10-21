# Overview

PythonArchTesting checks whether one or more target Python projects conform to a
reference project. The reference project declares expectations with annotation
metadata, and the CLI turns those declarations into rule results and reports.

## How It Works

1. Add rule declarations to the reference project.
2. Run the CLI against one target or many targets.
3. Read the report summary, then inspect the failing results.

The tool is declaration-driven and static by default. It reads source code and
annotations; it does not execute application behavior to decide whether a rule
passed. The one exception is opt-in: with `--dynamic`, the runtime rules run
the target in a separate interpreter to observe structure the source does not
show — calls between layers, attribute writes, imports by name, stage order.
They still never compare results ([dynamic-checks.md](dynamic-checks.md)).

## Supported Checks

All markers are imported from `pythonarchtesting.rules`. They group into five
categories. See [api-reference.md](api-reference.md) for every option and
[pattern-recipes.md](pattern-recipes.md) for ready-to-use combinations.

**Signature and shape** — describe the callable interface and the data layout
of a class:

- `required_entity_signature`, `required_method`, `require_method_set`,
  `require_member_set`, `required_constructor`, `required_factory`,
  `required_attribute`, `does_not_have`

**Imports** — module-scoped or package-scoped import policy, in either direct
AST mode or graph (reachable-import) mode:

- `forbid_imports`

**Type identity and inheritance** — structural conformance, inheritance, and
identity checks:

- `implements_protocol`, `subclass_of`, `exact_type`, `not_subclass_of`,
  `inherits_directly_from`, `is_enum`

**Abstractness and finality** — class-level and method-level modifiers:

- `is_abstract_class`, `is_concrete_class`, `is_final_class`,
  `is_non_final_class`, `is_abstract_method`, `is_non_abstract_method`,
  `is_final_method`, `is_non_final_method`

**Variable flow** — ordered stages of a tracked variable:

- `flow`, `enforce_flow`

**Runtime structure** — opt-in with `--dynamic`; executes the target, never
compares its results:

- `forbid_runtime_calls`, `require_runtime_calls` (layering by the calls that
  actually happen), `enforce_reference_calls` (the reference's call graph),
  `forbid_foreign_writes` (encapsulation), `forbid_runtime_instantiation`
  (dependency injection), the runtime counterparts of the class rules
  (`require_runtime_members`, `forbid_runtime_members`,
  `is_runtime_concrete_class`, `is_runtime_abstract_class`,
  `implements_runtime_protocol`), design patterns (`is_runtime_singleton`,
  `enforce_runtime_observer`, `require_runtime_delegation`),
  `forbid_runtime_imports`, and `enforce_flow` with `cases` (stage order learned
  from running the reference)

At report level, markers map to four evaluator families:

- `api_signature`
- `import_policy`
- `protocol_conformance`
- `variable_flow`

With `--dynamic`, runtime results form ten more families,
`runtime_calls`, `runtime_reference_calls`, `runtime_writes`,
`runtime_instances`, `runtime_members`, `runtime_class_kind`,
`runtime_protocol`, `runtime_pattern`, `runtime_imports`, and
`runtime_flow`.

## Declaration Placement

- Signature-level `Annotated[...]` is supported for
  `required_entity_signature` and `implements_protocol`.
- `__archtest__: Annotated[...]` is used for module, class, and body
  declarations such as `forbid_imports`, `required_method`,
  class-level `implements_protocol`, and `enforce_flow`.
- `flow(...)` is statement-level metadata and must appear immediately after the
  statement it annotates.
- Supported annotation containers are `Annotated`, `typing.Annotated`, and
  `typing_extensions.Annotated`.

## What It Does Not Do

PythonArchTesting is not a general code-quality suite. It does not currently
score:

- docstring quality
- style or formatting quality
- general lint findings unrelated to declared architectural rules
