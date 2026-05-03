# `is_concrete_class`

Require the matched target class to classify as concrete under the same local
static model used by `is_abstract_class(...)`.

- **Category:** Abstractness & finality
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import is_concrete_class
```

Use when the target class must have **no** unresolved abstract member names
after local-base propagation and concrete overrides are applied.

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
from pythonarchtesting.rules import is_concrete_class


class RepositoryImplementationContract:
    __archtest__: Annotated[None, is_concrete_class()]
```

## What it checks

- Absence of unresolved abstract member names after local-base propagation and concrete overrides.
- Static decorator intent on the matched target class and its local bases.

## What it does not check

- External abstract bases — only local resolution is performed.
- Runtime instantiability — the rule does not execute target code.
- Whether all methods have non-empty bodies — a `pass`-only method is still concrete.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [is_abstract_class](is_abstract_class.md) — the inverse classification
