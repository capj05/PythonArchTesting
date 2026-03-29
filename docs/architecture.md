# Architecture

The active pipeline is:

1. Parse reference entities and declaration metadata.
2. Normalize annotation declarations into a shared declaration model.
3. Compile supported declarations into rules.
4. Match source entities to target entities.
5. Evaluate compiled rules against each target.
6. Build reports from `RunState` and per-target results.

## Important Simplifications

- There is no config-driven architecture-rule compilation anymore.
- There is no structural evaluator anymore.
- Rule targets are declared with annotation metadata, using direct marker-factory metadata as the recommended style and strict literal tuples as an optional compatibility form inside `Annotated[...]`. Signature-level `Annotated[...]` is supported for function or method entity rules, and `__archtest__: Annotated[...]` remains the surface for module/class/body-only declarations.
- `src.rules.compilation` is the canonical compilation namespace; older `src.core.compilation` imports are compatibility-only.

## Supported Evaluation Families

- `api_signature`
- `import_policy`
- `protocol_conformance`
