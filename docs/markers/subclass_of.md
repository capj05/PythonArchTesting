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
# reference/repositories.py
from typing import Annotated
from pythonarchtesting.rules import subclass_of


class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, subclass_of("repositories.BaseRepository")]
```

The base is named by its module within the reference (without the
reference's own package name) and its class.

## What it checks

- The matched target class is a strict subclass (direct or transitive) of the matched target counterpart of the named source base.
- A failure has one violation and its fact in `details.facts` (aligned 1:1
  with `details.violations`): `kind` (`not_subclass`), `class` and
  `expected_base` (both `module:Class`, the submission's names), `file`,
  `line` (where the class is defined). When the base itself has no
  counterpart in the submission the result has no fact: that is no verdict
  on the class. Nor has a target that is the base itself: its violation
  says the rule is aimed at the base, not at a class derived from it.

## What it does not check

- Structural conformance — use [implements_protocol](implements_protocol.md) for that.
- Behavioral correctness of overridden methods.
- Identity equality with the base — that's [exact_type](exact_type.md).

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [exact_type](exact_type.md), [not_subclass_of](not_subclass_of.md), [inherits_directly_from](inherits_directly_from.md) — related nominal checks
