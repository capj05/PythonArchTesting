# Usage Guide

Rule declarations are metadata only. They do not enforce rules at import time; the CLI reads them from the reference project and evaluates them against one or more targets.

## Preferred Reference Style

Use annotation markers with `Annotated`. Preferred examples use direct marker calls from `src.rules`:

```python
from typing import Annotated
from src.rules import forbid_imports, required_entity_signature, required_method

__archtest__: Annotated[
    None,
    forbid_imports("statistics", scope="package", package="data_processor"),
]


def normalize_name(
    value: str,
) -> Annotated[
    str,
    required_entity_signature(mode="compatible", return_annotation="warning"),
]:
    return value.strip().title()


class Calculator:
    def add(self, a: int, b: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(signature_mode="compatible"),
        ]
        return a + b
```

This example covers:

- module-level `forbid_imports`
- function-level signature `required_entity_signature`
- method-level `required_method`
- class-level `implements_protocol`

## CLI

```bash
python -m src.cli --source example/project_1/reference --targets-dir example/project_1/assignments --format json
```

To validate reference declarations without analyzing targets:

```bash
python -m src.cli --validate-declarations --source example/project_1/reference --format json
```

For a declaration-only stub reference project, configure discovery to scan `.pyi` files:

```ini
[discovery]
included_file_patterns = *.pyi
```

You can also target specific projects:

```bash
python -m src.cli --source example/project_1/reference --target path/to/target_a --target path/to/target_b
```

## Validation Notes

- Invalid annotation declarations produce compiler evidence instead of crashing extraction or compilation.
- `python -m src.cli --validate-declarations` is the focused authoring and CI check for reference declarations.
- Declaration validation is source-only: it scans the reference/source project and does not analyze targets.
- Declaration validation returns a non-zero exit code for invalid declarations or source parsing/resolution errors.
- Reference code can declare `required_entity_signature` and `implements_protocol` in function or method signatures with `Annotated[...]`.
- Use `__archtest__: Annotated[...]` for module/class declarations and for body markers such as `forbid_imports` or `required_method`.
- Preferred metadata is direct marker calls imported from `src.rules`.
- Strict tuple metadata remains supported for compatibility or import-free authoring.

Example:

```python
from typing import Annotated
from src.rules import required_entity_signature

def normalize(
) -> Annotated[str, required_entity_signature(mode="compatible")]:
    return value.strip()
```

Stub-only example:

```python
from typing import Annotated
from src.rules import required_entity_signature

def add(
    a: int,
    b: int,
) -> Annotated[int, required_entity_signature(mode="exact")]: ...
```

## Placement And Limits

- Supported annotation containers are `Annotated`, `typing.Annotated`, and `typing_extensions.Annotated`.
- Signature declarations are supported only on function and method parameters or return annotations.
- Signature declarations support `required_entity_signature` and `implements_protocol` in v1.
- `implements_protocol` supports fully-qualified string references, symbol-style references such as `implements_protocol(Repository)`, parameterized references such as `implements_protocol(Repository[str])`, transparent wrappers such as `implements_protocol(Optional[Repository])` or `implements_protocol(Repository | None)`, and single-class containers such as `implements_protocol(list[Repository])` or `implements_protocol(dict[str, Repository])`.
- Signature-level target annotations for `implements_protocol` may also use transparent wrappers such as `Optional[RepoImpl]`, `RepoImpl | None`, `Annotated[RepoImpl, ...]`, or `type[RepoImpl]`, plus single-class containers such as `list[RepoImpl]`, `Sequence[RepoImpl]`, or `dict[str, RepoImpl]`, when they still reduce to one target-side class.
- Containers or unions that reduce to multiple distinct class candidates remain unsupported for protocol resolution in v1.
- `forbid_imports` and `required_method` still require existing non-signature declaration surfaces.
- Body markers must be simple top-level `__archtest__` annotated statements in the relevant module, class, function, or method body.
- Signature and body declarations are tracked independently when they appear on the same entity.
- Metadata entries must be either supported marker-factory expressions with AST-literal arguments/keyword values or strict literal tuples shaped as `(kind, params_dict)`.
- `required_method` is a method rule. It should be attached to methods, not classes.
- Prefer signature syntax for compact function or method entity rules. Prefer `__archtest__` when signatures would become noisy or when you need module/class/body-only rules.
- Declaration-only `.pyi` reference trees are supported when discovery is explicitly configured with `included_file_patterns = *.pyi`.
- Mixed `.py` and `.pyi` reference modules are not merged in v1. Use either a normal `.py` reference tree or a dedicated stub-only `.pyi` tree.

## Notes

- `list_comprehension` is removed.
- `[arch_rules]` and `[structural_check]` are removed.
- Reports should contain only the supported rule IDs.
