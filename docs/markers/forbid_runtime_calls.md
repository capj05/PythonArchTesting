# `forbid_runtime_calls`

Forbid the matched target function or method's module from calling directly
into given modules while it runs — a layering rule checked on the calls that
actually happen.

- **Category:** Runtime structure
- **Placement:** function- or method-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import forbid_runtime_calls
```

A controller that receives its service as a parameter has no import of the
repository, yet `service.repository.get(...)` reaches straight into the storage
layer. [`forbid_imports`](forbid_imports.md) cannot see that, because the
dependency travels through an object whose type the source does not state
(dependency injection, duck typing, `getattr`). This marker calls the target
with the declared cases and records every call that **code of the target's
module** makes into another module.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `*modules` (positional) | `str` | — | Dotted module names the code must not call; each also covers its submodules. |
| `cases` | `list[dict]` | — | Call arguments that drive the code, see [Cases](../dynamic-checks.md#cases). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `allow` | `list[str] \| None` | `None` | Modules exempt from `modules`, e.g. `["repository.queries"]` under a forbidden `"repository"`. |
| `init` | `dict \| None` | `None` | Methods only: constructor arguments for every case, `{"args": [...], "kwargs": {...}}`. |
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

Module names are those of the analysed project, without the package the root
is imported as (`"repository"`, not `"target_7.repository"`), or any other
importable module (`"sqlite3"`).

## Example

```python
from typing import Annotated, Any
from pythonarchtesting.rules import forbid_runtime_calls


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[
        None,
        forbid_runtime_calls(
            "repository",
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

A target whose controller calls `service.repository.get(...)` fails with
`case 0: handle_order calls repository:OrderRepository.get (line 17)`.
Worked example:
[`example/rule_showcase/dyn001_layers`](../../example/rule_showcase/dyn001_layers/).

## What it checks

- Direct calls from any code of the target's module — the entity itself and
  every helper of the same module it runs — into a function, method, or
  constructor of a forbidden module.
- Calls of C functions and methods of C types too: `pickle.dumps` (implemented
  in `_pickle`) is reported as `pickle`, `cursor.execute` as `sqlite3`.
- Calls made through objects passed in, attributes, `getattr`, or names
  computed at run time — whatever actually executes.

## What it does not check

- Indirect calls: when the target calls the service and the service calls the
  repository, only the first call belongs to the target's module. That is the
  layering the rule expresses.
- Calls of builtins (`len`, `print`, `list.append`) — they belong to no layer.
- Calls the cases do not reach; see [Cases](../dynamic-checks.md#cases).
- What the call computes. Results are never compared.

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [require_runtime_calls](require_runtime_calls.md) — the positive counterpart:
  the code must go through a layer
- [forbid_imports](forbid_imports.md) — the static policy on import statements
- [forbid_runtime_imports](forbid_runtime_imports.md) — imports performed while
  the module loads
