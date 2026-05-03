# `subclass_of`

Require the matched target class to inherit from the matched target counterpart
of a named source base.

- **Category:** Type identity & inheritance
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import subclass_of
```

Use to require nominal inheritance (direct or transitive). The matched base
itself does not satisfy the rule — there must be a strict subclass relation.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `base` (positional) | `str` | — | Dotted name of the source base class whose matched counterpart the target must subclass. |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import subclass_of


class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, subclass_of("reference.BaseRepository")]
```

## What it checks

- The matched target class is a strict subclass (direct or transitive) of the matched target counterpart of the named source base.

## What it does not check

- Structural conformance — use [implements_protocol](implements_protocol.md) for that.
- Behavioral correctness of overridden methods.
- Identity equality with the base — that's [exact_type](exact_type.md).

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [exact_type](exact_type.md), [not_subclass_of](not_subclass_of.md), [inherits_directly_from](inherits_directly_from.md) — related nominal checks
