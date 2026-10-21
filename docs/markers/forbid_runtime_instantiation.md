# `forbid_runtime_instantiation`

Require dependency injection: code of the matched target's module must not
create instances of classes from given modules — it has to receive them.

- **Category:** Runtime structure
- **Placement:** function- or method-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import forbid_runtime_instantiation
```

A service that is handed its repository can be tested with a fake one and
moved to another storage; a service that writes `OrderRepository()` itself
cannot. Both call the same repository methods, so
[`forbid_runtime_calls`](forbid_runtime_calls.md) cannot tell them apart. This
marker forbids the *creation* while still allowing the use.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `*modules` (positional) | `str` | — | Dotted module names whose classes must not be instantiated; each also covers its submodules. |
| `cases` | `list[dict]` | — | Call arguments that drive the code, see [Cases](../dynamic-checks.md#cases). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `allow` | `list[str] \| None` | `None` | Modules exempt from `modules`. |
| `init` | `dict \| None` | `None` | Methods only: constructor arguments for every case — this is where the injected object goes. |
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated, Any
from pythonarchtesting.rules import forbid_runtime_instantiation


class OrderService:
    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def place(self, order_id: str, prices: list[float]) -> Order:
        __archtest__: Annotated[
            None,
            forbid_runtime_instantiation(
                "repository",
                init={"args": [{"$new": "repository.OrderRepository"}]},
                cases=[{"args": ["A1", [10.0, 5.5]]}],
            ),
        ]
        order = Order(order_id, sum(prices))
        self._repository.save(order.order_id, order.total)
        return order
```

A target whose `__init__` ignores the argument and builds its own repository
fails with `case 0: service:OrderService.__init__ creates
repository:OrderRepository at service.py:18`. Worked example:
[`example/rule_showcase/dyn004_injection`](../../example/rule_showcase/dyn004_injection/).

## What it checks

- Instances of classes defined in the listed project modules, created by any
  code of the target's module while a case runs — for a method, **including
  building the instance**, so a dependency created in `__init__` is caught.
- Each object counts once, as its most derived class, however long its
  `super().__init__()` chain.
- Objects the case itself builds with `$new` are the caller's, not the
  target's, and do not count.

## What it does not check

- Classes outside the analysed project (`sqlite3.Connection`); forbid the
  call that creates them with [`forbid_runtime_calls`](forbid_runtime_calls.md).
- Objects created by other modules on the target's behalf (a factory module).
- Objects created through `cls.__new__` without `__init__`, or by `copy`/`pickle`.
- What the code computes. Results are never compared.

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [forbid_runtime_calls](forbid_runtime_calls.md) — forbid using a layer at all
- [required_constructor](required_constructor.md) — require the constructor
  parameter the dependency is injected through
