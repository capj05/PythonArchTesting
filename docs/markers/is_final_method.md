# `is_final_method`

Require the matched target method to be decorated with a recognized final
decorator.

- **Category:** Abstractness & finality
- **Placement:** method body `__archtest__: Annotated[...]`

## Usage

```python
from pythonarchtesting.rules import is_final_method
```

Use to require the target method to carry `@final`. Recognized decorators are
`final`, `typing.final`, and `typing_extensions.final`.

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

from pythonarchtesting.rules import is_final_method


class Renderer:
    def render(self) -> str:
        __archtest__: Annotated[None, is_final_method()]
        return ""
```

The matching target method must declare `@final` to satisfy this rule.

## What it checks

- Presence of a recognized final decorator on the matched target method.

## What it does not check

- Method kind (instance / classmethod / staticmethod) — use `required_method(..., enforce_method_kind=True)`.
- Class-level finality — use [is_final_class](is_final_class.md).
- Runtime override-prevention behavior.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [is_non_final_method](is_non_final_method.md) — the inverse
- [is_final_class](is_final_class.md) — the class-level form
