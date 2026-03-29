# API Reference

## Annotation Syntax

Preferred syntax is annotation-first. Use direct marker calls from `src.rules` inside `Annotated[...]`. Strict tuple metadata remains supported as an optional compatibility form. Signature-level metadata is supported for function and method rule declarations, and `__archtest__` markers remain the surface for module/class declarations, body-only rule kinds, and statement-level `flow(...)` markers:

```python
from typing import Annotated
from src.rules import enforce_flow, flow, forbid_imports, required_entity_signature

__archtest__: Annotated[
    None,
    forbid_imports("statistics", scope="package"),
]


def normalize(
    value: str,
) -> Annotated[
    str,
    required_entity_signature(mode="compatible", return_annotation="warning"),
]:
    value = value.strip()
    __archtest__: Annotated[None, flow("validated")]
    __archtest__: Annotated[None, enforce_flow(["validated"], variable="value")]
    return value
```

Placement and parsing rules:

- Supported containers are `Annotated`, `typing.Annotated`, and `typing_extensions.Annotated`.
- Signature declarations are supported only on function and method parameters or return annotations.
- Signature declarations support `required_entity_signature` and `implements_protocol`.
- `forbid_imports`, `required_method`, and `implements_protocol` still require their existing non-signature declaration surfaces.
- Body markers must be simple top-level `__archtest__` annotated statements in the relevant body.
- Statement-level `flow(...)` markers must appear immediately after the statement they annotate.
- If the same rule kind is declared in both places on one entity, the body marker takes precedence.
- Metadata entries must be either marker-factory expressions with AST-literal arguments/keyword values or strict literal tuples shaped as `(kind, params_dict)`.
- Invalid annotation declarations produce compiler evidence instead of crashing the pipeline.

## CLI Commands

- Normal analysis: `python -m src.cli --source <reference_root> --target <target_root>`
- Declaration validation: `python -m src.cli --validate-declarations --source <reference_root> [--reference-modules ...] [--format json]`

Declaration validation is source-only. It scans reference declarations, reports unsupported or invalid declaration issues, and exits non-zero when it finds invalid declarations or source parsing/resolution errors. Normal analysis remains unchanged: invalid declarations stay non-fatal and show up as compiler evidence in the usual pipeline.

Declaration-only reference stubs are supported in `.pyi` and `__init__.pyi` files when the source project is configured with:

```ini
[discovery]
included_file_patterns = *.pyi
```

This v1 support is intended for dedicated stub-only reference trees. Mixed `.py` and `.pyi` siblings for the same reference module are not merged.

## Rule Markers

### `required_entity_signature(...)`

Declares a required top-level signature on a matching target entity.

Common options:

- `mode`
- `allow_extra_params`
- `allow_param_rename`
- `return_annotation`
- `severity`

### `required_method(...)`

Declares a required compatible method.

Common options:

- `signature_mode`
- `enforce_method_kind`
- `severity`

Use this marker on methods, not on classes.

### `forbid_imports(*forbidden, **options)`

Declares a static import policy.

Common options:

- `scope`
- `package`
- `allow`
- `ignore_globs`
- `ignore_type_checking`
- `severity`

### `implements_protocol(protocol, **options)`

Declares protocol requirements for either:

- class-level structural conformance against a source-side protocol class
- function or method signature roles annotated with `Annotated[..., implements_protocol(...)]`

Common options:

- `signature_mode`
- `enforce_method_kind`
- `return_annotation`
- `severity`

`protocol` may be either a fully-qualified string reference or a symbol-style reference such as `implements_protocol(Repository)`.

### `flow(stage, **options)`

Declares a statement-level stage marker for a tracked variable in a function or method body.

Common options:

- `variable`

### `enforce_flow(stages, **options)`

Declares an ordered variable-flow requirement on a function or method.

Common options:

- `variable`
- `severity`

## Public Modules

- `src.rules`: public import path for annotation markers.

## Notes

- Unsupported annotation containers or metadata expressions are reported as compiler evidence.
- Prefer direct marker calls from `src.rules` for reference code; tuple metadata remains supported when you need compatibility or import-free declarations.
- Treat `src.rules.compilation` as the canonical compilation namespace for the supported annotation-first pipeline.

## Removed APIs

These names are no longer part of the public API:

- `list_comprehension`
- pattern decorators such as `detect_singleton`
- architecture decorators such as `forbid_dependencies` or `no_god_class`
