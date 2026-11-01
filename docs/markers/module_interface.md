# `module_interface`

Require other modules to use a module only through its interface: the names
it lists, or its public names.

- **Category:** Imports
- **Placement:** the module whose interface it states, module-level
  `__archtest__: Annotated[...]`
- **Runs:** the static check always; the runtime check (with `entry` and
  `cases`) only with `python-arch-test --dynamic`, otherwise it is `SKIPPED`.

## Usage

```python
from pythonarchtesting.rules import module_interface
```

A module that keeps helpers of its own (`_check_price`) can state that the
rest of the program may not reach them: the module-level counterpart of
[`forbid_foreign_writes`](forbid_foreign_writes.md), which protects an
object's attributes.

## Arguments

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `*names` (positional) | `str` | — | The module's top-level names other modules may use: functions, classes, module-level variables, names it imports (re-exports of a package) and its submodules. None given: its public names, those without a leading underscore (dunder names count as public). |
| `entry` | `str \| None` | `None` | A reference function or method, `"module.function"`, whose run the runtime check observes. |
| `cases` | `list[dict] \| None` | `None` | Calls of `entry`, in the [case language](../dynamic-checks.md#cases). Required together with `entry`. |
| `init` | `dict \| None` | `None` | Constructor arguments when `entry` is a method. |
| `ignore_type_checking` | `bool` | `True` | Leave out imports inside `if TYPE_CHECKING:`. |
| `timeout_s` | `float` | `5.0` | Time limit per run of the cases. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
# reference/models.py
from typing import Annotated

from pythonarchtesting.rules import module_interface

__archtest__: Annotated[
    None,
    module_interface(
        "Order",
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

- **Static (`DEP005`)**, in every other module of the target: each
  `from <module> import name` (relative or absolute) and each use reached
  through a name bound to the module (`from . import models` → `models.name`,
  `import pkg.models as m` → `m.name`, `import pkg.models` →
  `pkg.models.name`) must use a name of the interface. Imports inside
  functions count too. An absolute import may go through the target's own
  directory name or the reference's (a submission that imports itself under
  the reference's package name).
- **Runtime (`DYN012`)**, with `entry`, `cases` and `--dynamic`: every call
  another module makes into the module while `entry` runs must go to a name
  of the interface. A method of a public class is allowed: the object may
  have come out through the interface (a function that returns it).
- The names listed are translated to the target's through the matching, so a
  renamed entity is still judged as the reference's. The module is the target
  module the matching paired with the reference's; a renamed module needs an
  assisted-pairing mapping (`--mapping`).

## What it does not check

- Access through `getattr`, `importlib` or `vars()`.
- Reads of module-level variables (only calls at run time, imports and
  attribute uses statically).
- Uses within the module itself.
- `from <module> import *` (the star import names nothing to check).
- Private methods of a public class (`Order()._internal()`); the check is
  about the module's names, not a class's members.
- Imports one level deeper than the module (`from pkg.module.sub import _x`
  against an interface of `pkg.module`).
- A name a nested function declares `global` or `nonlocal` after an
  enclosing function bound it locally: it still counts as that local.

## See also

- [forbid_imports](forbid_imports.md) — which modules a module may import
- [forbid_foreign_writes](forbid_foreign_writes.md) — an object's attributes written only by its own methods
- [architecture_entry](architecture_entry.md) — the reference's module dependencies as the model
