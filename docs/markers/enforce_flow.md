# `enforce_flow`

Enforce an ordered sequence of variable-flow stages declared by `flow(...)`
markers within a function body.

- **Category:** Variable flow
- **Placement:** statement-level `__archtest__: Annotated[...]` inside the same function/method body that holds the `flow(...)` markers

## Usage

```python
from pythonarchtesting.rules import enforce_flow, flow
```

Use to require that the matched target function's control flow visits the
named stages of the named variable in the declared order. The companion
[flow](flow.md) markers identify each stage's program point.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `stages` (positional) | `list[str]` | — | Ordered list of flow-stage labels expected on every CFG path. |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `variable` | `str \| None` | `None` | Name of the variable whose flow stages must be ordered. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import enforce_flow, flow


def process(value: str) -> str:
    value = value.strip()
    __archtest__: Annotated[None, flow("raw", variable="value")]
    value = value.lower()
    __archtest__: Annotated[None, flow("normalized", variable="value")]
    __archtest__: Annotated[
        None,
        enforce_flow(["raw", "normalized"], variable="value"),
    ]
    return value
```

## What it checks

- All declared `stages` are reachable in the matched target function's CFG.
- Stages occur in the declared order along every path that visits them.
- The named `variable` is the same across the corresponding `flow` and `enforce_flow` markers.

## What it does not check

- Runtime values or transformations applied at each stage.
- Stages declared by `flow(...)` markers in other functions — scope is the enclosing function body.
- Side-effects or invariants between stages.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [flow](flow.md) — declares the stages that `enforce_flow` orders
