# `exact_type`

Require the matched target class to be exactly the matched target counterpart
of a named source base.

- **Category:** Type identity & inheritance
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import exact_type
```

Use when the target must be the matched base counterpart **itself** — no
subclass, no parallel class with the same name. Subclasses do not satisfy this
rule.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `base` (positional) | `str` | — | Dotted name of the source base class; the matched target must equal its counterpart exactly. |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import exact_type


class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, exact_type("reference.BaseRepository")]
```

## What it checks

- Identity equality of the matched target class with the matched counterpart of the named source base.

## What it does not check

- Subclass relations — use [subclass_of](subclass_of.md).
- Structural protocol conformance — use [implements_protocol](implements_protocol.md).

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [subclass_of](subclass_of.md), [inherits_directly_from](inherits_directly_from.md) — related nominal checks
