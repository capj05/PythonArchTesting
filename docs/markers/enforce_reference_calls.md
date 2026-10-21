# `enforce_reference_calls`

Require the target's runtime dependency graph to follow the reference's: run
both from the same entry point and allow only the module-to-module calls the
reference makes.

- **Category:** Runtime structure
- **Placement:** function- or method-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import enforce_reference_calls
```

[`forbid_runtime_calls`](forbid_runtime_calls.md) and
[`require_runtime_calls`](require_runtime_calls.md) state one layering rule for
one module, so a layered design needs a marker per layer and per direction.
This marker states none of them: the reference already *is* the intended
design. It is called with the cases, every call between two different modules
of the project is recorded — from the entry point down to the lowest layer —
and that set of edges (`controller -> service`, `service -> repository`, …)
becomes the allowed dependency graph for the target.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `cases` | `list[dict]` | — | Call arguments that drive both runs, see [Cases](../dynamic-checks.md#cases). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `require_all` | `bool` | `False` | Also require every edge of the reference in each case: no layer may be skipped. |
| `init` | `dict \| None` | `None` | Methods only: constructor arguments for every case. |
| `timeout_s` | `float` | `5.0` | Wall-clock limit per run, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated, Any
from pythonarchtesting.rules import enforce_reference_calls


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[
        None,
        enforce_reference_calls(
            require_all=True,
            cases=[{"args": [
                {"id": "A1", "prices": [10.0, 5.5]},
                {"$new": "service.OrderService", "args": [
                    {"$new": "repository.OrderRepository"},
                    {"$new": "notifier.Notifier"},
                ]},
            ]}],
        ),
    ]
    total = service.place(request["id"], request["prices"])
    return {"status": "ok", "total": total}
```

The reference makes `controller -> service`, `service -> repository`, and
`service -> notifier`. A target whose notifier looks the total up in the
repository fails with `case 0: notifier -> repository is not in the reference
(Notifier.order_placed calls repository:OrderRepository.get …)` — a violation
two layers below the marked function. Worked example:
[`example/rule_showcase/dyn001_reference_calls`](../../example/rule_showcase/dyn001_reference_calls/).

## What it checks

- Per case, every call from code of one project module into another project
  module, anywhere in the call tree of the entry point. Module names are
  compared without the package the root is imported as, so the reference
  package and a target package named differently compare alike (the package's
  own `__init__.py` is `__init__`).
- With `require_all`: per case, every reference edge also occurs in the target.
- The reference has to run: a case whose arguments cannot be built for it is
  reported as `ERROR` (`reference_failed`).

The result lists both kinds of difference, in the terms of reflexion models
(Murphy et al.): `details.divergences` are edges the target makes and the
reference does not, which always fail the rule; `details.absences` are edges
of the reference the target never made, which fail it only with
`require_all` and are otherwise counted in the summary of a pass. An absence
names the lines of the target that did not run in that case, if any, since the
missing edge may sit on one of them. A pass also reports the lines no case ran
([What a pass means](../dynamic-checks.md#what-a-pass-means)).

## What it does not check

- Calls within one module, and calls into the standard library or third-party
  packages — only edges between project modules form the graph.
- How many times an edge is used, or in what order.
- Which function of the other module is called: `service -> repository` is one
  edge whether the code calls `save` or `get`.
- What the code computes. Results are never compared.

## Security

The reference and the target are executed; see
[Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [forbid_runtime_calls](forbid_runtime_calls.md),
  [require_runtime_calls](require_runtime_calls.md) — explicit rules for one
  module, when the reference should not be the specification
- [enforce_flow](enforce_flow.md) — runtime stage order, also learned from the
  reference
