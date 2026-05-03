# `not_subclass_of`

Forbid the matched target class from inheriting from or equalling the matched
counterpart of a named source base.

- **Category:** Type identity & inheritance
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import not_subclass_of
```

Use to forbid nominal inheritance from a specific base. The forbidden base
itself, direct subclasses, and transitive subclasses all fail.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `base` (positional) | `str` | — | Dotted name of the source base class whose matched counterpart the target must not subclass. |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of


class BaseRepository:
    pass


class CsvRepository:
    __archtest__: Annotated[None, not_subclass_of("reference.BaseRepository")]
```

## What it checks

- The matched target class is not equal to and not a subclass (direct or transitive) of the matched counterpart of the named source base.

## What it does not check

- Structural protocol conformance — use [implements_protocol](implements_protocol.md).
- Mixin or composition relationships beyond inheritance.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [subclass_of](subclass_of.md) — the positive form
