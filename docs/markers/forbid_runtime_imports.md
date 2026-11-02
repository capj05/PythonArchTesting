# `forbid_runtime_imports`

Forbid modules that the matched target module actually imports when it is
loaded — including imports by name that the static import graph cannot see.

- **Category:** Runtime structure
- **Placement:** module `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import forbid_runtime_imports
```

[`forbid_imports`](forbid_imports.md) reads `import` statements from the source.
It cannot follow `importlib.import_module("sql" + "ite3")` or
`__import__(name)`, because the module name only exists at runtime. This marker
imports the target module in a child interpreter and records every import its
code performs through `import` statements, `__import__`, `importlib.__import__`,
or `importlib.import_module`. The module is loaded without running the
`__init__.py` of the packages around it: a package that re-exports its
application (`from .wiring import serve`) would otherwise load every adapter
with any submodule, and those imports are the package's, not the module's.
What the module imports itself, also through other modules of the project,
counts. A module that needs names from its own package's `__init__.py` is
imported the ordinary way instead.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `*forbidden` (positional) | `str` | — | Dotted module names to forbid; each also forbids its submodules. |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `allow` | `list[str] \| None` | `None` | Modules exempt from `forbidden`, e.g. `["xml.sax.saxutils"]` under a forbidden `"xml"`. |
| `timeout_s` | `float` | `5.0` | Wall-clock limit for the child interpreter, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

A module of the project is named as in the reference, without the package the
root is imported as: `"repository"` forbids `from . import repository`. When
the target keeps that module under another name, the name of the matched
module is forbidden instead (`storage` for a `repository.py` renamed to
`storage.py`); a target module that holds several of the reference's modules
keeps the reference name, since forbidding it would forbid the others too.

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import forbid_runtime_imports

__archtest__: Annotated[
    None,
    forbid_runtime_imports("sqlite3", "pickle", "xml", allow=["xml.sax.saxutils"]),
]
```

A worked example is in
[`example/rule_showcase/dyn002_runtime_imports`](../../example/rule_showcase/dyn002_runtime_imports/).

## What it checks

- Imports executed while the target module is imported: `import` and
  `from ... import` statements, `importlib.import_module(...)`,
  `importlib.__import__(...)`, and `__import__(...)`, wherever their names come
  from. `from x.y import z` counts as `x.y.z`, the same as `import x.y.z`.
- Imports of the target's own modules imported along the way — a forbidden
  import in a helper module the target loads is reported with that helper's
  file and line. When the target root is a package, its `__init__.py` runs
  before any module in it, so its imports count for every module rule.
- Relative imports, resolved to absolute names before matching.

## What it does not check

- Imports inside functions that importing the module does not call. A
  module pulled in lazily and then used is caught by
  [`forbid_runtime_calls`](forbid_runtime_calls.md) on that function.
- Imports the standard library or third-party packages make on their own
  behalf: only imports executed from files under the target root count.
- Code paths that importing the module does not take (a branch on an
  environment variable, for example).
- Loading through lower-level machinery — `importlib.util.spec_from_file_location`
  plus `exec_module`, `importlib._bootstrap`, or `exec("import x", {})`, whose
  globals carry no file under the target root. These are deliberate evasions,
  not ordinary imports; review the source if they matter.

## Security

The target module is executed. See [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [forbid_imports](forbid_imports.md) — the static import policy, which needs no
  execution and also covers code that is never run
- [forbid_runtime_calls](forbid_runtime_calls.md) — calls into a module while a function runs
