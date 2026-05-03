# `flow`

Mark a stage in an ordered variable-flow contract within a function body.

- **Category:** Variable flow
- **Placement:** statement-level `__archtest__: Annotated[...]` inside a function/method body

## Usage

```python
from pythonarchtesting.rules import flow
```

Use to declare that, by the point the marker statement appears, a named
variable must have reached the named stage. `flow` markers compose with
[enforce_flow](enforce_flow.md) to form an ordered sequence checked against
the target function's control-flow graph.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `stage` (positional) | `str` | — | Flow-stage label recorded at this program point. |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `variable` | `str \| None` | `None` | Name of the variable whose flow this stage marks. |
| `message` | `str` | `None` | Custom violation message override. |

Severity is fixed to `"info"` for `flow` markers and is not a configurable argument.

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import flow


def process(value: str) -> str:
    cleaned = value.strip()
    __archtest__: Annotated[None, flow("cleaned", variable="cleaned")]
    return cleaned
```

## What it checks

- The named `variable` has been assigned by the marker's program point in the source function's CFG.
- The stage identifier is recorded in source order for downstream `enforce_flow` evaluation.

## What it does not check

- The actual value of the variable at runtime — analysis is static.
- Stage ordering on its own — pair with [enforce_flow](enforce_flow.md) to enforce ordering.
- Side-effects between stages.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [enforce_flow](enforce_flow.md) — pairs with `flow` to enforce stage ordering
