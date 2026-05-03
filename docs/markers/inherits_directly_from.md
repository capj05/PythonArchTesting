# `inherits_directly_from`

Require the matched target class to list the matched counterpart of a named
source base among its **immediate** bases.

- **Category:** Type identity & inheritance
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import inherits_directly_from
```

Use when the target class must inherit directly — a deeper transitive ancestor
does not satisfy this rule, and the matched base itself does not satisfy it
either.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `base` (positional) | `str` | — | Dotted name of the source base class; the matched counterpart must appear in the target's immediate base list. |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import inherits_directly_from


class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[
        None,
        inherits_directly_from("reference.BaseRepository"),
    ]
```

## What it checks

- The matched counterpart of the named source base appears in the immediate base list of the matched target class.

## What it does not check

- Transitive ancestry beyond the direct base list — use [subclass_of](subclass_of.md) for that.
- Structural protocol conformance — use [implements_protocol](implements_protocol.md).

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [subclass_of](subclass_of.md), [exact_type](exact_type.md) — related nominal checks
