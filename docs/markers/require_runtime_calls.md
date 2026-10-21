# `require_runtime_calls`

Require the matched target function or method's module to call directly into
given modules while it runs — the work must be delegated to that layer, not
done in place.

- **Category:** Runtime structure
- **Placement:** function- or method-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import require_runtime_calls
```

A controller that sums the prices itself instead of asking the service has
the same signature and imports as one that delegates. Calling it shows the
difference: the delegating one calls into `service`, the other never does.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `*modules` (positional) | `str` | — | Dotted module names the code must call; a call into a submodule counts. |
| `cases` | `list[dict]` | — | Call arguments that drive the code, see [Cases](../dynamic-checks.md#cases). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `init` | `dict \| None` | `None` | Methods only: constructor arguments for every case. |
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

`allow` is not accepted; it only makes sense for
[forbid_runtime_calls](forbid_runtime_calls.md).

## Example

```python
from typing import Annotated, Any
from pythonarchtesting.rules import require_runtime_calls


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[
        None,
        require_runtime_calls(
            "service",
            cases=[{"args": [
                {"id": "A1", "prices": [10.0, 5.5]},
                {"$new": "service.OrderService",
                 "args": [{"$new": "repository.OrderRepository"}]},
            ]}],
        ),
    ]
    total = service.place(request["id"], request["prices"])
    return {"status": "ok", "total": total}
```

A target that computes the total itself fails with
`case 0: no direct call into service`. Worked example:
[`example/rule_showcase/dyn001_layers`](../../example/rule_showcase/dyn001_layers/).

## What it checks

- In **every** case, at least one direct call from code of the target's module
  into each listed module. Choose cases on the path that must delegate; a case
  that legitimately returns early (validation) belongs to a separate rule
  without it.
- When a case raised before reaching the layer, the message says so.

## What it does not check

- Which function of the layer is called, or how often.
- Calls made on the target's behalf by other modules (indirect calls).
- What the call computes.

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [forbid_runtime_calls](forbid_runtime_calls.md) — calls into a layer that
  must not be reached
- [enforce_flow](enforce_flow.md) — the order of processing stages
