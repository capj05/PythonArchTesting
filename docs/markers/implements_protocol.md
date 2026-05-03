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
| `protocol` (positional) | `str` | — | Dotted name of the source Protocol to satisfy (e.g. `"reference.Repository"`). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `signature_mode` | `str` | `"compatible"` | Signature matching mode for protocol methods: `"compatible"`, `"exact"`, or `"any"`. |
| `enforce_method_kind` | `bool` | `True` | Require method-kind parity (instance / classmethod / staticmethod) between Protocol and target. |
| `return_annotation` | `str` | `"warning"` | Return-type checking level: `"warning"`, `"error"`, or `"ignore"`. |
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
- Parameter compatibility under `signature_mode`.
- Method-kind parity (instance / classmethod / staticmethod) when `enforce_method_kind=True`.
- Return annotation handling per `return_annotation`.

## What it does not check

- Protocol attributes that are pure data (no methods).
- Runtime registration via `@runtime_checkable` or `isinstance` checks.
- Behavioral correctness of the methods.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [subclass_of](subclass_of.md) — for nominal inheritance instead of structural conformance
