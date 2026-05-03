# `is_abstract_method`

Require the matched target method to be decorated with a recognized abstract
decorator.

- **Category:** Abstractness & finality
- **Placement:** method body `__archtest__: Annotated[...]`

## Usage

```python
from pythonarchtesting.rules import is_abstract_method
```

Use to require the target method to carry an abstract decorator. Recognized
forms are `abstractmethod`, `abc.abstractmethod`, `abstractclassmethod`,
`abstractstaticmethod`, and `abstractproperty` after import alias normalization
where available.

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

from pythonarchtesting.rules import is_abstract_method


class Renderer:
    def render(self) -> str:
        __archtest__: Annotated[None, is_abstract_method()]
        raise NotImplementedError
```

The matching target method must declare e.g. `@abstractmethod` to satisfy this
rule.

## What it checks

- Presence of a recognized abstract decorator on the matched target method.

## What it does not check

- Method kind (instance / classmethod / staticmethod) — use `required_method(..., enforce_method_kind=True)` or `require_method_set(method_kind=...)`.
- Whether the method body actually raises `NotImplementedError`.
- Class-level abstractness — use [is_abstract_class](is_abstract_class.md).

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [is_non_abstract_method](is_non_abstract_method.md) — the inverse
- [is_abstract_class](is_abstract_class.md) — the class-level form
