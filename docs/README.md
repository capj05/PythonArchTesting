# Documentation

The supported rule surface is intentionally small:

- `required_entity_signature`
- `required_method`
- `forbid_imports`

Use annotation-based declarations with `Annotated[...]`. Preferred examples use direct marker calls from `src.rules`, while strict tuple metadata remains supported as a compatibility form. Signature-level `Annotated[...]` metadata is supported for function and method `required_entity_signature` rules, while `__archtest__: Annotated[...]` remains the public surface for module/class and body-only rules.

Recommended entry points:

1. [overview.md](overview.md)
2. [usage-guide.md](usage-guide.md)
3. [configuration.md](configuration.md)
4. [api-reference.md](api-reference.md)
5. [architecture.md](architecture.md)
