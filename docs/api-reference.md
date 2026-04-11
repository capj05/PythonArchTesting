# API Reference

## Supported Public API

The supported module entrypoints are:

- `pythonarchtesting.state`
- `pythonarchtesting.runner_multi`

Supported symbols under `pythonarchtesting.state`:

- `ValidationStatus`
- `ValidationResult`
- `rule_result_to_validation`
- `MemoryManager`
- `ModuleDiscovery`
- `ProjectState`

Supported symbols under `pythonarchtesting.runner_multi`:

- `prepare_source`
- `evaluate_target`
- `run_multi`

Deep import paths and historical compatibility aliases are not part of the
supported public API.

## CLI Entrypoints

- `python-arch-test`: preferred installed-package command for most users
- `python -m pythonarchtesting.cli`: developer-oriented module entrypoint for source checkouts

## CLI Flags

- `--config`
- `--source`
- `--target`
- `--targets`
- `--targets-dir`
- `--reference-modules`
- `--project-pattern`
- `--exclude-patterns`
- `--format {json,markdown}`
- `--output`
- `--validate-declarations`
- `--validation-scope {all,logical-views}`

## Supported Annotation Containers

The declaration reader supports:

- `Annotated`
- `typing.Annotated`
- `typing_extensions.Annotated`

Strict tuple metadata also remains supported as a compatibility form:

```python
("required_entity_signature", {"mode": "compatible"})
```

## Marker Factories From `pythonarchtesting.rules`

### Placement Summary

| Marker | Purpose | Valid placement |
| --- | --- | --- |
| `required_entity_signature(...)` | Require a compatible function or method signature | Signature-level `Annotated[...]` on parameters or return annotations |
| `required_method(...)` | Require a method with a compatible signature | `__archtest__: Annotated[...]` inside a method body |
| `forbid_imports(...)` | Forbid imports in a declared scope | `__archtest__: Annotated[...]`, commonly at module level |
| `implements_protocol(...)` | Require structural protocol conformance | Class-level `__archtest__: Annotated[...]` or signature-level `Annotated[...]` |
| `flow(...)` | Mark a statement as a named flow stage | Statement-level `__archtest__: Annotated[...]` immediately after the statement |
| `enforce_flow(...)` | Require ordered flow stages for a variable | `__archtest__: Annotated[...]` in a function or method body |

### `required_entity_signature(...)`

Common options:

- `mode`
- `allow_extra_params`
- `allow_param_rename`
- `return_annotation`
- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature


def normalize(
    value: str,
) -> Annotated[
    str,
    required_entity_signature(mode="compatible", return_annotation="warning"),
]:
    return value.strip()
```

### `required_method(...)`

Common options:

- `signature_mode`
- `enforce_method_kind`
- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_method


class Calculator:
    def add(self, a: int, b: int) -> int:
        __archtest__: Annotated[None, required_method(signature_mode="compatible")]
        return a + b
```

### `forbid_imports(...)`

Common options:

- `scope`
- `package`
- `mode`
- `ignore_type_checking`
- `allow`
- `ignore_globs`
- `severity`
- `message`

Notes:

- `mode="reachable"` is the default contract.
- `mode="direct"` preserves the current direct AST import check.
- In Phase 1, `mode="reachable"` reports an `ERROR` because reachability analysis is not implemented yet.

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

__archtest__: Annotated[
    None,
    forbid_imports(
        "statistics",
        scope="package",
        package="data_processor",
        mode="direct",
    ),
]
```

### `implements_protocol(...)`

Common options:

- `protocol`
- `signature_mode`
- `enforce_method_kind`
- `return_annotation`
- `severity`
- `message`

Examples:

```python
from typing import Annotated
from pythonarchtesting.rules import implements_protocol


class RepositoryAdapter:
    __archtest__: Annotated[None, implements_protocol("reference.Repository")]
```

```python
from typing import Annotated
from pythonarchtesting.rules import implements_protocol


def build(
    repo: Annotated[object, implements_protocol("reference.Repository")],
) -> Annotated[object, implements_protocol("reference.Repository")]:
    return repo
```

### `flow(...)`

Common options:

- `stage`
- `variable`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import flow


def process(value: str) -> str:
    cleaned = value.strip()
    __archtest__: Annotated[None, flow("cleaned", variable="cleaned")]
    return cleaned
```

### `enforce_flow(...)`

Common options:

- `stages`
- `variable`
- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import enforce_flow, flow


def process(value: str) -> str:
    value = value.strip()
    __archtest__: Annotated[None, flow("raw", variable="value")]
    value = value.lower()
    __archtest__: Annotated[None, flow("normalized", variable="value")]
    __archtest__: Annotated[
        None,
        enforce_flow(["raw", "normalized"], variable="value"),
    ]
    return value
```

## Placement Rules

- Signature-level declarations are supported for
  `required_entity_signature` and `implements_protocol`.
- Use `__archtest__: Annotated[...]` for module, class, and body declarations.
- `flow(...)` must appear immediately after the statement it annotates.
- Signature and body declarations on the same entity are tracked separately.
- Invalid declarations remain non-fatal in normal analysis and are reported as
  compiler evidence.
- `--validate-declarations` is the focused source-only check for declaration
  authoring and CI.

## Stub-Only Reference Trees

Declaration-only reference trees are supported with `.pyi` files when discovery
is configured with:

```ini
[discovery]
included_file_patterns = *.pyi
```

Mixed `.py` and `.pyi` siblings for the same reference module are not merged.
