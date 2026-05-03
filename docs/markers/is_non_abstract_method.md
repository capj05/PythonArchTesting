# `is_non_abstract_method`

Forbid the matched target method from being decorated with a recognized
abstract decorator.

- **Category:** Abstractness & finality
- **Placement:** method body `__archtest__: Annotated[...]`

## Usage

```python
from pythonarchtesting.rules import is_non_abstract_method
```

Use to require the target method to be implemented. The rule fails when the
matched target carries `abstractmethod`, `abc.abstractmethod`,
`abstractclassmethod`, `abstractstaticmethod`, or `abstractproperty`, and
passes otherwise.

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

from pythonarchtesting.rules import is_non_abstract_method


class Renderer:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_abstract_method()]
        return ""
```

## What it checks

- Absence of a recognized abstract decorator on the matched target method.

## What it does not check

- Whether the method body is non-trivial — a `pass`-only body still satisfies the rule.
- Method kind (instance / classmethod / staticmethod) — use `required_method(..., enforce_method_kind=True)`.
- Class-level abstractness — use [is_concrete_class](is_concrete_class.md).

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [is_abstract_method](is_abstract_method.md) — the positive form
