# `is_non_final_class`

Forbid the matched target class from being decorated with a recognized
final-class decorator.

- **Category:** Abstractness & finality
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import is_non_final_class
```

Use to require the target class to be subclassable. The rule fails when the
matched target carries `@final` (or `typing.final` / `typing_extensions.final`)
and passes otherwise.

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
from pythonarchtesting.rules import is_non_final_class


class Plugin:
    __archtest__: Annotated[None, is_non_final_class()]
```

## What it checks

- Absence of a recognized final-class decorator on the matched target class.

## What it does not check

- Whether the class is actually subclassed somewhere.
- Method-level `@final` usage — that does not affect this rule.
- Runtime subclass behavior.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [is_final_class](is_final_class.md) — the positive form
