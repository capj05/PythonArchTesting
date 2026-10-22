# `require_runtime_members`

Require every instance of the matched target class, as actually built, to
have given members — however they got there.

- **Category:** Runtime structure
- **Placement:** class-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import require_runtime_members
```

[`required_attribute`](required_attribute.md) reads the class body. It sees
`self.port = ...` and, with `include_dynamic_attributes`, a literal
`setattr(self, "port", ...)` — but not a `setattr` in a loop over a dict, a
`self.__dict__.update(...)`, a mixin, a decorator, or a base class from a
library. This marker builds an instance from each case's constructor
arguments and looks at the object itself.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `*names` (positional) | `str` | — | Member names every instance must have. |
| `cases` | `list[dict]` | — | Constructor arguments (`args`, `kwargs`), one instance per case, see [Cases](../dynamic-checks.md#cases). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `types` | `dict[str, str] \| None` | `None` | Member name → class (`{"repository": "repository.OrderRepository"}`): the member must hold an instance of that class or a subclass. The class is named as in [`$new`](../dynamic-checks.md#cases), by the reference's name; a target that renamed the module or the class is checked against its matched class. |
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated, Any
from pythonarchtesting.rules import require_runtime_members

DEFAULTS = {"host": "localhost", "port": 5432, "debug": False}


class Settings:
    __archtest__: Annotated[
        None,
        require_runtime_members(
            "host", "port", "debug",
            cases=[{"args": [{}]}, {"args": [{"port": 6543}]}],
        ),
    ]

    def __init__(self, overrides: dict[str, Any]) -> None:
        values = {**DEFAULTS, **overrides}
        for key in DEFAULTS:
            setattr(self, key, values[key])
```

A target that only copies the keys it was given fails on the first case with
`case 0: the instance has no 'debug'`. Worked example:
[`example/rule_showcase/dyn005_runtime_members`](../../example/rule_showcase/dyn005_runtime_members/).

## What it checks

- Each name on the built instance: in its `__dict__`, on its class or any base
  (methods, class attributes, properties, slots), or provided by
  `__getattr__`. The result records where the member came from.
- That an instance can be built at all: a constructor that raises fails the
  case.
- With `types`: what the member holds on the built instance is an instance of
  the class (`isinstance`, so a subclass passes). A violation reads
  `case 0: 'repository' is a dict, not an instance of repository.OrderRepository`.

## What it does not check

- The member's value or annotation, or its type unless `types` names it — see
  [required_attribute](required_attribute.md) for the declared shape.
- Members that appear only after other method calls, unless the case calls
  them first with `steps` ([Cases](../dynamic-checks.md#cases)).

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [forbid_runtime_members](forbid_runtime_members.md) — members an instance must not have
- [required_attribute](required_attribute.md), [require_member_set](require_member_set.md) — the static checks
