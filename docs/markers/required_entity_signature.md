# `required_entity_signature`

Require a function or method to expose a compatible signature on the matched
target.

- **Category:** Signature & shape
- **Placement:** signature-level `Annotated[...]` (return annotation or parameter annotation)

## Usage

```python
from pythonarchtesting.rules import required_entity_signature
```

Place the marker inside an `Annotated[...]` on a parameter or return annotation
of the source function or method. The matched target callable must expose a
compatible signature.

## Arguments

**Required:**

_None — the marker takes only optional arguments._

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `mode` | `str` | `"compatible"` | Signature matching mode: `"compatible"`, `"exact"`, or `"any"`. |
| `allow_extra_params` | `bool` | `True` | Accept target signatures with extra optional parameters. |
| `allow_param_rename` | `bool` | `False` | Allow parameter-name differences when matching. |
| `return_annotation` | `str` | `"warning"` | Return-type checking level: `"warning"`, `"error"`, or `"ignore"`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

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

## What it checks

- Parameter shape on the matched target (arity, kind, defaults) under `mode="compatible"` or `mode="exact"`.
- Async/sync parity between source and target.
- Return-annotation presence or compatibility when `return_annotation` is enabled.

## What it does not check

- Function or method body behavior — purely a signature check.
- Docstrings, decorators, or type-aliased return values beyond the configured `return_annotation` mode.
- Implementations attached to instance objects at runtime.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [required_method](required_method.md) — same model for class methods
