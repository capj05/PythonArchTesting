# `enforce_runtime_observer`

Require the matched target class to act as an Observer subject: registered
listeners are notified, and unsubscribed ones no longer are.

- **Category:** Runtime structure
- **Placement:** class-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import enforce_runtime_observer
```

Having `subscribe` and `publish` methods (which [`required_method`](required_method.md)
can demand) does not make a class an Observer subject; calling the listeners
does. The probe builds the subject, registers its own recording listener, and
watches whether it is called. The listener is callable and answers any method
(`listener(event)`, `listener.update(event)`, `listener.on_event(...)`), so the
target's calling convention does not matter.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `subscribe` | `str` | — | Method that registers a listener; called with the listener as its last argument, after `subscribe_args` (as its only argument without them). |
| `notify` | `str` | — | Method that notifies listeners. |
| `cases` | `list[dict]` | — | Constructor arguments of the subject (`args`, `kwargs`). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `notify_args` | `list \| None` | `None` | Arguments passed to `notify`; `$new` objects allowed. |
| `unsubscribe` | `str \| None` | `None` | Method that removes the listener; when given, a second notification must not reach it. |
| `subscribe_args` | `list \| None` | `None` | Arguments passed before the listener to `subscribe` and `unsubscribe`, for a subject keyed by event: `subscribe_args=["created"]` calls `subscribe("created", listener)`. |
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated, Any

from pythonarchtesting.rules import enforce_runtime_observer


class EventBus:
    __archtest__: Annotated[
        None,
        enforce_runtime_observer(
            subscribe="subscribe", notify="publish", unsubscribe="unsubscribe",
            notify_args=["order_placed"], cases=[{"args": []}],
        ),
    ]
    ...
```

A target whose `unsubscribe` does nothing fails with `case 0: the listener
was still called after unsubscribe()`. Worked example:
[`example/rule_showcase/dyn008_patterns`](../../example/rule_showcase/dyn008_patterns/).

## What it checks

- After `subscribe(listener)` and `notify(*notify_args)`, the listener was
  called at least once (directly or through any of its methods).
- With `unsubscribe`: after `unsubscribe(listener)`, another `notify` does
  not call it.
- `subscribe`, `notify`, and `unsubscribe` are the reference's method names;
  a target whose matched class renamed a method is called by its own name.

## What it does not check

- What the listener receives, or how many times it is called.
- Listener ordering, weak references, or thread safety.

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [is_runtime_singleton](is_runtime_singleton.md), [require_runtime_delegation](require_runtime_delegation.md)
