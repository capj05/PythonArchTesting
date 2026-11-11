# `implements_protocol`

Require structural conformance to a named Protocol.

- **Category:** Type identity & inheritance
- **Placement:** class-body `__archtest__: Annotated[...]`, or signature-level `Annotated[...]` on parameter or return annotations
## Usage

```python
from pythonarchtesting.rules import implements_protocol
```

Use to require a target class (or callable parameter) to satisfy a Protocol's
methods structurally. Resolution is by dotted name relative to the reference
project.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `protocol` (positional) | `str \| Protocol class` | — | The source Protocol to satisfy, as a reference to its class or its dotted name (e.g. `"reference.Repository"`). A second positional argument is a warning and is not used (see [Positional Arguments](README.md#positional-arguments)). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `signature_mode` | `str` | `"compatible"` | Signature matching mode for protocol methods: `"compatible"`, `"exact"`, or `"any"`. |
| `enforce_method_kind` | `bool` | `True` | Require method-kind parity (instance / classmethod / staticmethod) between Protocol and target. |
| `return_annotation` | `str` | `"warning"` | Return-type checking level: `"warning"`, `"error"`, or `"off"`; any other value makes the declaration invalid (see [Logical And Enumerated Arguments](README.md#logical-and-enumerated-arguments)). |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import implements_protocol


class RepositoryAdapter:
    __archtest__: Annotated[None, implements_protocol("reference.Repository")]
```

## What it checks

- Presence of every Protocol method on the matched target class.
- Parameter compatibility under `signature_mode`. Under `"compatible"` the
  target may add parameters only if callers can leave them out (a default,
  or `*args` / `**kwargs`); an extra required parameter fails, since a
  caller of the port does not pass it.
- Class names in annotations are resolved through imports, relative ones
  too, and through a package that re-exports the class (`from ..domain import
  Appointment` where `domain/__init__.py` imports it from `domain/schedule.py`).
- Method-kind parity (instance / classmethod / staticmethod) when `enforce_method_kind=True`.
- Return annotation handling per `return_annotation`.

## What it does not check

- Protocol attributes that are pure data (no methods).
- Runtime registration via `@runtime_checkable` or `isinstance` checks.
- Behavioral correctness of the methods.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [subclass_of](subclass_of.md) — for nominal inheritance instead of structural conformance
- [implements_runtime_protocol](implements_runtime_protocol.md) — conformance of a built instance, members attached at run time included
