# `forbid_imports`

Forbid one or more imports in a declared scope.

- **Category:** Imports
- **Placement:** module `__archtest__: Annotated[...]` (most common); also valid as `__archtest__` declarations within package `__init__.py`
## Usage

```python
from pythonarchtesting.rules import forbid_imports
```

Use to keep an import out of a single module or out of a whole package
subtree. Bare `forbid_imports(...)` defaults to `mode="reachable"` (graph
analysis); pass `mode="direct"` for an AST-only direct-import check.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `*forbidden` (positional) | `str` | — | One or more dotted module or package names to forbid (e.g. `"requests"`, `"sqlalchemy"`). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `scope` | `str` | `"package"` | Scope of the policy: `"module"`, `"package"`, or the legacy alias `"entity"` (= module). |
| `package` | `str \| None` | `None` | Package dotted name when `scope="package"`; required for package scope. |
| `mode` | `str` | `"reachable"` | Analysis mode: `"reachable"` (graph-based transitive imports) or `"direct"` (AST-only direct imports). |
| `ignore_type_checking` | `bool` | `True` | Exclude imports inside `if TYPE_CHECKING:` guards from analysis. |
| `allow` | `list[str] \| None` | `None` | Submodules or symbols exempt from the forbidden list. |
| `ignore_globs` | `list[str] \| None` | `None` | Glob patterns for files to exclude from the import scan. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated

from pythonarchtesting.rules import forbid_imports

from .repository import InMemoryOrderRepository

__archtest__: Annotated[
    None,
    forbid_imports("requests", scope="package", package="storage"),
]

__all__ = ["InMemoryOrderRepository"]
```

## What it checks

- Direct AST imports of a forbidden module under `mode="direct"`.
- Reachable imports through transitive imports under `mode="reachable"` (default).
- Module scope (`scope="module"`) or package scope (`scope="package"` with `package=...`).
- `TYPE_CHECKING` guarded imports are ignored by default; flip `ignore_type_checking=False` to include them.

## What it does not check

- Imports inside `try/except ImportError:` blocks beyond the static AST.
- Lazy / deferred imports done through `importlib` or string lookups.
- Imports in files filtered out by `ignore_globs`.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [../pattern-recipes.md](../pattern-recipes.md) — package-scope policy patterns
