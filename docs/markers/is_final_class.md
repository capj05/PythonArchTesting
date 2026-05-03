# `is_final_class`

Require the matched target class to be decorated with a recognized final-class
decorator.

- **Category:** Abstractness & finality
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import is_final_class
```

Use to require the target class to carry `@final`. Recognized decorators are
`final`, `typing.final`, and `typing_extensions.final` after import alias
normalization where available.

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
from pythonarchtesting.rules import is_final_class


class ValueObjectContract:
    __archtest__: Annotated[None, is_final_class()]
```

## What it checks

- Presence of a recognized final-class decorator on the matched target class.

## What it does not check

- Finality inferred from comments or naming — only decorators count.
- Method-level `@final` usage — that does not satisfy the class rule. Use [is_final_method](is_final_method.md) for that.
- Runtime subclass-prevention behavior.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [is_non_final_class](is_non_final_class.md) — the inverse
- [is_final_method](is_final_method.md) — the method-level form
