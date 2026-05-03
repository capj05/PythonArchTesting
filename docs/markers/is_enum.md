# `is_enum`

Require the matched target class to classify as enum-like based on stdlib enum
inheritance.

- **Category:** Abstractness & finality
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import is_enum
```

Use to require a target class to be an enum. The rule passes when the matched
target class directly inherits from `enum.Enum`, `enum.IntEnum`, `enum.StrEnum`,
`enum.Flag`, or `enum.IntFlag`, or from a local class that is itself enum-like.

## Arguments

**Required:**

_None — the marker takes only optional arguments._

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import is_enum


class StatusContract:
    __archtest__: Annotated[None, is_enum()]
```

## What it checks

- Direct inheritance from a recognized stdlib enum base (`Enum`, `IntEnum`, `StrEnum`, `Flag`, `IntFlag`).
- Transitive inheritance through a local enum-like class.

## What it does not check

- Uppercase-constant naming as enum evidence — naming alone does not classify a class as enum-like.
- Unresolved third-party enum bases — the rule uses local resolution only.
- A specific enum family — there is no discriminator parameter to require, e.g., `IntEnum` specifically.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [subclass_of](subclass_of.md) — for nominal base matching of a specific class
