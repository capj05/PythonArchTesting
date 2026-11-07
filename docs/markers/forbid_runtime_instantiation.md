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
| `*modules` (positional) | `str` | — | Dotted module names whose classes must not be instantiated, each also covering its submodules; or qualified class names (`"discounts.PercentDiscount"`), each forbidding that class only. A class the target builds that matches no reference class counts when it lives in the module of a named class and looks like one (a renamed or new strategy): a named class or one of its reference bases is among its bases, or it defines a public method named like one of theirs; a value class, a dataclass or an exception of that module that does neither, and a matched class not named, stay allowed. The likeness is by name only: a helper there with a method named like a named class's counts. |
| `cases` | `list[dict]` | — | Call arguments that drive the code, see [Cases](../dynamic-checks.md#cases). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `allow` | `list[str] \| None` | `None` | Modules exempt from `modules`. |
| `transitive` | `bool` | `False` | Also count objects other project code builds while the target runs — a factory module of its own. |
| `through` | `list[str] \| None` | `None` | With `transitive=True`: modules whose code may build the objects, e.g. the forbidden module itself building its internals. |
| `init` | `dict \| None` | `None` | Methods only: constructor arguments for every case — this is where the injected object goes. |
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated, Any
from pythonarchtesting.rules import forbid_runtime_instantiation

from .models import Order


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
- Each violation has a fact in `details.facts`, aligned 1:1 with
  `details.violations`: `kind` (`instance`), `case`, `creator` (the target's
  code the object is charged to, `module:qualname`), `class`
  (`module:Class`), `file` and `line` (where the object was built), and
  `via` (with `transitive=True` the code it was built through, outermost
  first; else empty).

### Factories (`transitive=True`)

By default an object counts against the code that constructed it: a service
that calls `factory.make_repository()` passes, because `OrderRepository()` ran
in `factory`. With `transitive=True`, an object built by any project code
while code of the target's module is further up the stack counts as well,
and the violation names the chain:

```text
case 0: service:OrderService.place -> factory:make_repository creates repository:OrderRepository at factory.py:5
```

Code of the forbidden module itself then counts too — the repository
building a `Row` while saving — so name it in `through`:
`forbid_runtime_instantiation("repository", transitive=True,
through=["repository"], ...)`. An object built by code of a `through` module,
or by code that one called, is not the target's doing.

## What it does not check

- Classes outside the analysed project (`sqlite3.Connection`); forbid the
  call that creates them with [`forbid_runtime_calls`](forbid_runtime_calls.md).
- Objects created by other modules on the target's behalf (a factory module),
  unless `transitive=True`.
- Objects created through `cls.__new__` without `__init__`, or by `copy`/`pickle`.
- What the code computes. Results are never compared.
- A collaborator rebuilt from the injected one's class (`self._bus =
  type(bus)()`) when `init` injects a `$spy`: the spy's class cannot be built
  that way, the case does not run and nothing is judged. Inject real objects
  with `$new`, and put the spies of a delegation marker in that marker's own
  `init`.

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [forbid_runtime_calls](forbid_runtime_calls.md) — forbid using a layer at all
- [required_constructor](required_constructor.md) — require the constructor
  parameter the dependency is injected through
