# Overview

PythonArchTesting checks whether one or more target Python projects conform to a
reference project. The reference project declares expectations with annotation
metadata, and the CLI turns those declarations into rule results and reports.

## How It Works

1. Add rule declarations to the reference project.
2. Run the CLI against one target or many targets.
3. Read the report summary, then inspect the failing results.

The tool is static and declaration-driven. It reads source code and annotations;
it does not execute application behavior to decide whether a rule passed.

## Supported Checks

The current public marker surface from `pythonarchtesting.rules` is:

- `required_entity_signature`: require a compatible function or method
  signature
- `required_method`: require a method to exist with a compatible signature
- `forbid_imports`: declare a forbidden import policy
- `implements_protocol`: require structural conformance to a protocol
- `flow`: mark a statement as a stage in variable flow
- `enforce_flow`: require stages to appear in order for a tracked variable

At report level, these map to four evaluation families:

- `api_signature`
- `import_policy`
- `protocol_conformance`
- `variable_flow`

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
