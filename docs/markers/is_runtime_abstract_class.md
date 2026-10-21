# `is_runtime_abstract_class`

Require the matched target class to be abstract as Python sees it, bases
outside the project included. Nothing is instantiated.

- **Category:** Runtime structure
- **Placement:** class-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import is_runtime_abstract_class
```

A base class meant to be extended (`Storage`) must keep at least one abstract
method. [`is_abstract_class`](is_abstract_class.md) answers that from the
source; this marker imports the module and asks `inspect.isabstract`, so
abstract methods from `abc`-based library classes and metaclass tricks count
as Python counts them.

## Arguments

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `timeout_s` | `float` | `5.0` | Wall-clock limit for importing the module, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

No `cases`: the class is never instantiated.

## Example

```python
from abc import ABC, abstractmethod
from typing import Annotated
from pythonarchtesting.rules import is_runtime_abstract_class


class Storage(ABC):
    __archtest__: Annotated[None, is_runtime_abstract_class()]

    @abstractmethod
    def save(self, inventory: "Inventory") -> None: ...
```

A target that implements `save` fails with `the class is concrete at run time:
no abstract method is left unimplemented`. Worked example:
[`example/rule_showcase/dyn006_runtime_classes`](../../example/rule_showcase/dyn006_runtime_classes/).

## What it checks

- `inspect.isabstract(cls)` on the imported class.

## What it does not check

- Which methods are abstract — only that at least one is.

## Security

The target module is imported; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [is_runtime_concrete_class](is_runtime_concrete_class.md)
- [is_abstract_class](is_abstract_class.md) — the static check
