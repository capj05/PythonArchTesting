# `forbid_cycles`

Forbid dependency cycles between the project's modules.

- **Category:** Imports
- **Placement:** the reference's root `__init__.py`, module-level
  `__archtest__: Annotated[...]`; anywhere else the declaration is invalid
  (see [Other Invalid Argument Values](README.md#other-invalid-argument-values))
- **Runs:** the static check always; the runtime check (with `entry` and
  `cases`) only with `python-arch-test --dynamic`, otherwise it is `SKIPPED`.

## Usage

```python
from pythonarchtesting.rules import forbid_cycles
```

Two modules that depend on each other cannot be understood, tested or
replaced one without the other. A cycle needs no marker naming its modules:
one declaration covers the whole program.

## Arguments

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
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

from pythonarchtesting.rules import forbid_cycles

__archtest__: Annotated[None, forbid_cycles()]
```

## What it checks

- **Static (`DEP003`)**: every group of modules that reach each other through
  import statements (strongly connected components, Tarjan's algorithm). All
  import statements count, also those inside a function: an import moved into
  a function hides a cycle from Python's import machinery, not from the
  design. Each cycle is reported with one shortest path through it and the
  file and line of every import on the path (`details.cycles`).
- **Runtime (`DYN010`)**, with `entry`, `cases` and `--dynamic`: cycles in the
  calls between modules while `entry` runs, on the reference and on the
  target. A cycle counts only if the reference does not have it: an observer
  that calls back into its subscriber forms a cycle of calls by design. A
  module the reference does not have counts as part of the modules that call
  it.
- Imports are the same however they are spelled: relative (`from .repository
  import X`), absolute through the target's own directory name
  (`from target.repository import X`), or absolute through the reference's
  package name (a submission that imports itself as the reference does). A
  target directory named like a real library would hide that library's
  imports; name submission directories so they cannot clash.

## What it does not check

- Imports done through `importlib` or strings.
- `from pkg import sub` of a submodule is an import of `pkg.sub`, not of
  `pkg`, so a package `__init__.py` that re-exports its submodules does not
  form a cycle with them by that alone.
- Calls that no case drives.

## See also

- [enforce_layers](enforce_layers.md) — one layer order for the whole program
- [forbid_imports](forbid_imports.md) — one module's import policy
- [../dynamic-checks.md](../dynamic-checks.md) — how runtime checks run
