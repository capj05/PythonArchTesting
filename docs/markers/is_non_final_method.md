# `is_non_final_method`

Forbid the matched target method from being decorated with a recognized final
decorator.

- **Category:** Abstractness & finality
- **Placement:** method body `__archtest__: Annotated[...]`

## Usage

```python
from pythonarchtesting.rules import is_non_final_method
```

Use to require the target method to remain overridable. The rule fails when
the matched target carries `@final` (or `typing.final` /
`typing_extensions.final`) and passes otherwise.

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

from pythonarchtesting.rules import is_non_final_method


class Renderer:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_final_method()]
        return ""
```

## What it checks

- Absence of a recognized final decorator on the matched target method.

## What it does not check

- Whether the method is actually overridden somewhere.
- Method kind (instance / classmethod / staticmethod).
- Class-level finality — use [is_non_final_class](is_non_final_class.md).

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [is_final_method](is_final_method.md) — the positive form
