# `is_runtime_concrete_class`

Require the matched target class to be instantiable as Python sees it —
including abstract methods inherited from bases outside the project.

- **Category:** Runtime structure
- **Placement:** class-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import is_runtime_concrete_class
```

[`is_concrete_class`](is_concrete_class.md) resolves abstract bases only within
the project. A class deriving from `collections.abc.MutableMapping` must
implement `__getitem__`, `__setitem__`, `__delitem__`, `__iter__`, and
`__len__` — a list the standard library defines. This marker lets Python
decide: the class is imported, checked with `inspect.isabstract`, and built
from each case.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `cases` | `list[dict]` | — | Constructor arguments (`args`, `kwargs`), see [Cases](../dynamic-checks.md#cases). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from collections.abc import MutableMapping
from typing import Annotated
from pythonarchtesting.rules import is_runtime_concrete_class


class Inventory(MutableMapping[str, int]):
    __archtest__: Annotated[None, is_runtime_concrete_class(cases=[{"args": []}])]
    ...
```

A target that forgets `__len__` fails with `case 0: the class is abstract at
run time; unimplemented: __len__`. Worked example:
[`example/rule_showcase/dyn006_runtime_classes`](../../example/rule_showcase/dyn006_runtime_classes/).

## What it checks

- No abstract method is left, as Python computes it over the whole MRO.
- The constructor succeeds with each case's arguments.

## What it does not check

- Whether the implemented methods do anything sensible.

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [is_runtime_abstract_class](is_runtime_abstract_class.md)
- [is_concrete_class](is_concrete_class.md) — the static check
