# `is_abstract_class`

Require the matched target class to classify as abstract under conservative
local static analysis.

- **Category:** Abstractness & finality
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import is_abstract_class
```

Use when the target class must have at least one unresolved abstract member
after combining: abstract methods declared on the class, unresolved abstract
member names inherited from local base classes, and concrete overrides
declared on the class.

Recognized abstract decorators: `abstractmethod`, `abc.abstractmethod`, and the
legacy `abstractclassmethod`, `abstractstaticmethod`, `abstractproperty` forms.

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
from pythonarchtesting.rules import is_abstract_class


class RepositoryContract:
    __archtest__: Annotated[None, is_abstract_class()]
```

## What it checks

- Presence of one or more unresolved abstract member names after local-base propagation and concrete overrides are applied.
- Static decorator intent on the matched target class and its local bases.

## What it does not check

- External abstract base classes — third-party abstractness is not expanded into inferred obligations.
- Runtime behavior — the rule does not execute target code.
- Method-level abstractness in isolation — use [is_abstract_method](is_abstract_method.md) for that.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [is_concrete_class](is_concrete_class.md) — the inverse classification
- [is_abstract_method](is_abstract_method.md) — the method-level form
