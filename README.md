# PythonArchTesting

PythonArchTesting compares target projects against a reference project with rule declarations and reports only the supported rule families:

- `required_entity_signature`
- `required_method`
- `forbid_imports`
- `implements_protocol`

Use annotation-based declarations to declare rule targets. Function and method entity rules can use signature-level `Annotated[...]` metadata, while module, class, and body-only rules still use `__archtest__: Annotated[...]`. The primary style uses marker factories from `src.rules`, and strict tuple metadata remains supported as an optional compatibility form.

The project no longer supports `list_comprehension`, config-driven `arch_rules`, or `structural_check`. Config files that still use `[arch_rules]` or `[structural_check]` now fail validation.

## Installation

Runtime use:

```bash
pip install -r requirements.txt
```

Development and docs tooling:

```bash
pip install -r requirements-dev.txt
```

Package contributors can also install the project with dev extras:

```bash
pip install -e .[dev]
```

## Quick Start

Reference code:

```python
from typing import Annotated
from src.rules import forbid_imports, required_entity_signature

__archtest__: Annotated[
    None,
    forbid_imports("statistics", scope="package", package="data_processor"),
]


def normalize(
    value: str,
) -> Annotated[
    str,
    required_entity_signature(mode="compatible", return_annotation="warning"),
]:
    return value.strip().lower()
```

CLI:

```bash
python -m src.cli --source example/project_1/reference --targets-dir example/project_1/assignments --format json
```

Declaration validation:

```bash
python -m src.cli --validate-declarations --source example/project_1/reference --format json
```

Stub-only reference projects:

```ini
[discovery]
included_file_patterns = *.pyi
```

```python
from typing import Annotated
from src.rules import required_entity_signature

def add(
    a: int,
    b: int,
) -> Annotated[int, required_entity_signature(mode="exact")]: ...
```

## Declarations

- Preferred syntax is direct marker metadata such as `Annotated[..., required_method(...)]`.
- `src.rules` is the public import path for marker factories.
- Use signature-level `Annotated[...]` metadata for function and method `required_entity_signature` declarations.
- Use `__archtest__: Annotated[...]` for module/class declarations and for rule kinds that are not supported in signatures.
- `implements_protocol` is a class-level declaration and must use `__archtest__: Annotated[...]`.
- Tuple metadata remains supported as a compatibility form and is strict in v1: exactly `(kind, params_dict)`.
- Invalid declarations remain non-fatal during normal analysis runs and are reported as compiler evidence.
- Use `--validate-declarations` as a focused source-only check for reference projects and CI.
- Declaration-only reference projects can use `.pyi` files when `[discovery].included_file_patterns` is set to `*.pyi`.
- Stub support is v1-only for dedicated `.pyi` reference trees; mixed `.py` and `.pyi` siblings are intentionally out of scope.

## Configuration

Supported top-level config sections include:

- `[discovery]`
- `[import]`
- `[logging]`
- `[error_handling]`
- `[files]`
- `[performance]`
- `[memory]`
- `[reporting]`
- `[matching]`
- `[output]`
- `[report]`
- `[reference]`
- `[projects]`

See [docs/usage-guide.md](docs/usage-guide.md), [docs/configuration.md](docs/configuration.md), and [docs/api-reference.md](docs/api-reference.md) for the supported surface.
