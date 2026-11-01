# `enforce_layers`

Require the whole project to follow one layer order: a higher layer may use a
lower one, never the reverse.

- **Category:** Imports
- **Placement:** the reference's root `__init__.py`, module-level
  `__archtest__: Annotated[...]`
- **Runs:** the static check always; the runtime check (with `entry` and
  `cases`) only with `python-arch-test --dynamic`, otherwise it is `SKIPPED`.

## Usage

```python
from pythonarchtesting.rules import enforce_layers
```

One declaration states the layering of the whole program, where
[`forbid_imports`](forbid_imports.md) needs a marker per module and per
direction. The notation is import-linter's `layers` contract, so the same
architecture can be checked by both tools.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `*layers` (positional) | `str` | — | The reference's modules from the highest layer to the lowest. `"a \| b"` puts independent siblings in one layer (neither may use the other), `"a : b"` siblings that may use each other. A name covers the module and everything inside it (`"app"` covers `app.views`). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `closed` | `list[str] \| None` | `None` | Layers, named by one of their modules, that no higher layer may bypass: whatever lies below a closed layer is reached through it. The lowest layer cannot be closed. |
| `ignore_type_checking` | `bool` | `True` | Leave out imports inside `if TYPE_CHECKING:`. |
| `entry` | `str \| None` | `None` | A reference function or method, `"module.function"` or `"module.Class.method"`, whose calls the runtime check observes. |
| `cases` | `list[dict] \| None` | `None` | Calls of `entry`, in the [case language](../dynamic-checks.md#cases). Required together with `entry`. |
| `init` | `dict \| None` | `None` | Constructor arguments when `entry` is a method. |
| `timeout_s` | `float` | `5.0` | Time limit per run of the cases. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
# reference/__init__.py
from typing import Annotated

from pythonarchtesting.rules import enforce_layers

__archtest__: Annotated[
    None,
    enforce_layers(
        "controller",
        "service",
        "repository | pricing | events",
        "models",
        closed=["service"],
        entry="controller.handle_order",
        cases=[{"args": [{"id": "A1", "prices": [10.0]},
                         {"$new": "service.OrderService",
                          "args": [{"$new": "repository.OrderRepository"},
                                   {"$new": "pricing.NoDiscount"},
                                   {"$new": "events.EventBus"}]}]}],
    ),
]
```

## What it checks

- **Static (`DEP002`)**, on every import statement of the target, at module
  level or inside a function (a lazy import still makes one module depend on
  another), as import-linter does:
  - a lower layer that imports a higher one (`upward`);
  - independent siblings that import each other (`sibling`);
  - a layer that imports one below a closed layer (`skip`);
  - also through modules that no layer names (`repository -> helpers ->
    controller`); a chain is not followed through another layer, whose own
    imports are judged on their own.
- **Runtime (`DYN009`)**, with `entry`, `cases` and `--dynamic`: the same
  order on the calls one module made into another while `entry` ran, on the
  reference and on the target. A call counts only if the reference does not
  make it too, so a callback or an injected port that calls "upwards" by
  design is not a violation. This is how a bypass that needs no import is
  caught: a controller that reaches the repository through the service's
  attribute (`service.repository.find(...)`) makes a call past the closed
  service.
- Target modules are named by the reference modules they were matched to, so
  a renamed module is still checked as its layer. A module the reference does
  not have counts, at run time, as part of the modules that call it (as with
  `enforce_reference_calls(allow_new_modules=True)`).

## What it does not check

- At run time only direct calls are judged: two calls recorded in different
  contexts do not make a chain.
- Calls that no case drives; the coverage note of a pass lists the lines of
  the entry's module that did not run.
- Imports done through `importlib` or strings.
- `closed` has no counterpart in import-linter 2.15's configuration.

## See also

- [forbid_cycles](forbid_cycles.md) — no two modules depend on each other
- [forbid_imports](forbid_imports.md) — one module's import policy
- [enforce_reference_calls](enforce_reference_calls.md) — the reference's exact call graph
- [../dynamic-checks.md](../dynamic-checks.md) — how runtime checks run
