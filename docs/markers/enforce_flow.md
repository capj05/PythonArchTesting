# `enforce_flow`

Enforce an ordered sequence of variable-flow stages declared by `flow(...)`
markers within a function body.

- **Category:** Variable flow
- **Placement:** statement-level `__archtest__: Annotated[...]` inside the same function/method body that holds the `flow(...)` markers
- **Runtime variant:** with `cases`, the rule (`FLW002`) runs only with `python-arch-test --dynamic` (see [Runtime check with `cases`](#runtime-check-with-cases)); without `cases` the static check always runs.

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
| `cases` | `list[dict] \| None` | `None` | Call arguments (`args`, `kwargs`, `init`) that switch the rule to the [runtime check](#runtime-check-with-cases). |
| `init` | `dict \| None` | `None` | Runtime check on a method only: `{"args": [...], "kwargs": {...}}` for constructing the instance; a case's own `init` overrides it. |
| `timeout_s` | `float` | `5.0` | Runtime check only: wall-clock limit per interpreter run, in `(0, 60]`. |
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

## Runtime check with `cases`

The static check reads `flow(...)` markers **in the target**, so every target
has to repeat them. Give `cases` instead and the rule (`FLW002`) runs with
`--dynamic`:

1. The reference function runs on each case. While a statement labelled by a
   `flow(...)` marker runs, the functions and methods of the project it
   calls directly are recorded as that stage's operations. A marker after an
   `if` or `for` labels the whole block, whose own operations are the calls
   outside the stages inside it; a stage inside a loop is recorded once per
   iteration.
2. The target runs on the same cases, and every call it makes into a
   function of the project, at any depth, is recorded in order.
3. The target passes when it calls each stage's operations in the
   reference's stage order. Other calls in between are allowed, as extra
   statements are in the static check. The reference's functions are
   translated to the target's through entity matching, so a renamed or moved
   step still counts.

```python
def import_record(line: str, sink: list) -> dict:
    record = steps.parse(line)
    __archtest__: Annotated[None, flow("parsed", variable="record")]
    record = steps.validate(record)
    __archtest__: Annotated[None, flow("validated", variable="record")]
    steps.store(record, sink)
    __archtest__: Annotated[None, flow("stored", variable="record")]
    __archtest__: Annotated[
        None,
        enforce_flow(
            ["parsed", "validated", "stored"],
            variable="record",
            cases=[{"args": ["ada;36", []]}],
        ),
    ]
    return record
```

A target that stores before validating fails, whatever it stores; one that
computes different records through the same steps passes. Values are never
recorded or compared. Calls into the standard library and builtins
(`str.strip`) are not operations of the program's structure: a stage that
calls no project function cannot be recognised in a target, and the result
lists it under `unchecked_stages`; if no stage calls one, the rule reports
`ERROR` (`reference_stages_call_nothing`). Without `--dynamic` the rule is
`SKIPPED`; with `cases` the static marker check is not run at all. For a
method, `init` gives the constructor arguments, as for the other runtime
rules.

The reference must reach every declared stage on every case — pick arguments
that take each branch — otherwise the rule reports `ERROR` with
`reference_misses_stage`.
Worked example: [`example/rule_showcase/flw002_runtime_flow`](../../example/rule_showcase/flw002_runtime_flow/).

## What it checks

- All declared `stages` are reachable in the matched target function's CFG.
- Stages occur in the declared order along every path that visits them.
- The named `variable` is the same across the corresponding `flow` and `enforce_flow` markers.
- With `cases` and `--dynamic`: the target runs the reference's stages in
  order, without any markers in the target; the project functions a stage
  calls identify the stage.

## What it does not check

- The function's result or any intermediate value: with `cases`, only the
  order of the stages' calls is compared.
- Stages declared by `flow(...)` markers in other functions — scope is the enclosing function body.
- Side-effects or invariants between stages.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [flow](flow.md) — declares the stages that `enforce_flow` orders
