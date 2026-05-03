# `required_constructor`

Require a class to expose a compatible `__init__` or `__new__`.

- **Category:** Signature & shape
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import required_constructor
```

Use when constructor shape is part of the API contract. By default the marker
prefers `__init__`, falls back to `__new__`, accepts inherited constructors,
and infers a dataclass-generated `__init__` on both source and target.

## Arguments

**Required:**

_None — the marker takes only optional arguments._

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `signature_mode` | `str` | `"compatible"` | Signature matching mode for the constructor: `"compatible"`, `"exact"`, or `"any"`. |
| `constructor_kind` | `str` | `"auto"` | Constructor preference: `"auto"` (prefer `__init__`, fall back to `__new__`), `"init"`, or `"new"`. |
| `allow_inherited` | `bool` | `True` | Accept a constructor inherited from a base class as a satisfying candidate. |
| `allow_missing` | `bool` | `False` | Pass when no candidate constructor exists on the target instead of failing. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import required_constructor


class User:
    __archtest__: Annotated[None, required_constructor()]

    def __init__(self, name: str) -> None:
        self.name = name
```

## What it checks

- Presence of a constructor candidate on the matched target under the configured `constructor_kind` and `allow_inherited` scope.
- Parameter compatibility under `signature_mode` ("compatible", "exact", or "any"), receiver-stripped.
- Statically recognizable dataclass-generated `__init__` on both reference and target.

## What it does not check

- Return annotations or method-kind (regular vs. classmethod vs. staticmethod).
- Constructor body or side effects.
- Metaclass `__call__`.
- Factory classmethods or staticmethods — use `required_factory(...)` for those.

## See also

- [../api-reference.md](../api-reference.md) — full option surface and dataclass examples
- [required_factory](required_factory.md) — for classmethod / staticmethod factories
