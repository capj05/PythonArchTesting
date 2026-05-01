# Usage Guide

This guide walks through the normal user flow:

1. write declarations in the reference project
2. validate those declarations
3. run one target or many targets
4. read the report in the right order

For most users, install the package and use `python-arch-test`. The
`python -m pythonarchtesting.cli` entrypoint is mainly useful when working from a source
checkout during development.

Examples in this guide come from `example/checkout_assignment/`, the
canonical worked example shipped with the repo. Every path and code fence
below corresponds to a real file you can open in the tree.

## 1. Write Reference Declarations

Module-level import policy plus a class-body cluster declaring required
attributes and a compatible constructor:

<!-- File: example/checkout_assignment/reference/storage/__init__.py -->
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

<!-- File: example/checkout_assignment/reference/models.py -->
```python
from typing import Annotated

from pythonarchtesting.rules import required_attribute, required_constructor


class Product:
    """Catalog product. Constructor shape and instance attributes are part of the API."""

    __archtest__: Annotated[
        None,
        required_attribute("sku", annotation="str", storage="instance"),
        required_attribute("name", annotation="str", storage="instance"),
        required_attribute("price", annotation="float", storage="instance"),
        required_constructor(signature_mode="compatible"),
    ]

    def __init__(self, sku: str, name: str, price: float) -> None:
        self.sku: str = sku
        self.name: str = name
        self.price: float = price
```

`forbid_imports(...)` uses `scope="module"` for file-wide checks and
`scope="package"` for package-subtree checks. The legacy `scope="entity"`
spelling is still accepted for compatibility, but `module` is the canonical
public name. Bare `forbid_imports(...)` defaults to reachable mode; use
`mode="direct"` when you want the direct AST import check instead.

Other supported declaration shapes — an in-method `required_factory` and a
class-level `implements_protocol`:

<!-- File: example/checkout_assignment/reference/models.py -->
```python
from typing import Annotated

from pythonarchtesting.rules import required_factory


class Cart:
    """Mutable cart of products. Provides an explicit ``empty()`` factory."""

    @classmethod
    def empty(cls) -> "Cart":
        __archtest__: Annotated[  # noqa: F842
            None,
            required_factory(
                satisfy_with=("classmethod",),
                name_match="exact",
                aliases=("empty",),
            ),
        ]
        return cls()
```

<!-- File: example/checkout_assignment/reference/storage/repository.py -->
```python
from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import implements_protocol

from ..contracts import OrderRepository
from ..models import Order


class InMemoryOrderRepository:
    """Repository implementation that satisfies ``OrderRepository``."""

    __archtest__: Annotated[
        None,
        implements_protocol(
            OrderRepository,
            signature_mode="compatible",
            return_annotation="error",
        ),
    ]

    def __init__(self) -> None:
        self._items: dict[str, Order] = {}

    def save(self, order: Order) -> Order:
        self._items[order.id] = order
        return order

    def get(self, order_id: str) -> Order:
        return self._items[order_id]
```

## 2. Validate Declarations First

Use declaration validation to catch invalid metadata before comparing targets:

```bash
python-arch-test --validate-declarations --source example/checkout_assignment/reference --format json
```

What this does:

- scans the reference project only
- reports invalid declarations, syntax errors, and source-resolution errors
- exits non-zero when declaration validation finds an error

The JSON shape starts with:

```json
{
  "mode": "validate-declarations",
  "summary": {
    "diagnostics_total": 0,
    "errors_total": 0,
    "files_scanned": 3,
    "invalid_declarations": 0
  },
  "diagnostics": []
}
```

## 3. Run One Or More Targets

Every run uses the same execution path. A single `--target` produces the same
JSON schema as a batch run — `targets` array with one entry and a `summary`.

```bash
python-arch-test --source example/checkout_assignment/reference --target example/checkout_assignment/assignments/target1 --format json
```

## 4. Run Multiple Targets

Batch analysis from a directory:

```bash
python-arch-test --source example/checkout_assignment/reference --targets-dir example/checkout_assignment/assignments --format json
```

Explicit target list:

```bash
python-arch-test --source example/checkout_assignment/reference --target example/checkout_assignment/assignments/target1 --target example/checkout_assignment/assignments/target3 --format json
```

Target discovery controls:

- `--targets-dir` scans subdirectories
- `--project-pattern` filters those subdirectories
- `--exclude-patterns` removes unwanted matches

## 5. Generate A Markdown Bundle

Markdown output always requires `--output` pointing to a directory, whether you
are running one target or many:

```bash
python-arch-test --source example/checkout_assignment/reference --targets-dir example/checkout_assignment/assignments --format markdown --output example/checkout_assignment/reports/report_md
```

The bundle contains:

- `report.md`: run-level summary and links to targets
- `targets/<target_id>.md`: one page per target

## 6. Use `--validation-scope` Only When You Mean It

The default scope is `all`.

Use `--validation-scope logical-views` only when you intentionally want the run
limited to template-style logical view functions detected from calls such as:

- `render_template(...)`
- `TemplateResponse(...)`
- `render(..., "template.html")`

For most projects, keep the default:

```bash
python-arch-test --validate-declarations --source example/checkout_assignment/reference --validation-scope all --format json
```

## 7. Read Results In This Order

For run-report JSON, start with:

```json
{
  "exit_code": 1,
  "summary": {
    "targets_total": 5,
    "targets_failed": 4,
    "targets_passed": 1,
    "results": {
      "results_total": 25,
      "status_counts": {
        "FAILED": 14,
        "OK": 8,
        "SKIPPED": 3
      }
    }
  }
}
```

Then inspect the failing target summary and one failing result:

```json
{
  "target_id": "target5",
  "summary": {
    "status_counts": {
      "FAILED": 3,
      "OK": 1,
      "SKIPPED": 1
    }
  },
  "results": [
    {
      "rule_id": "API001/required_entity_signature/v1",
      "status": "FAILED",
      "severity": "error",
      "message": "Required target entity missing or not matchable (status=unmatched, confidence=0.0).",
      "fix_hints": [
        "Match the required parameter names, kinds, and required/optional shape."
      ]
    }
  ]
}
```

Read the fields in this order:

1. `summary`
2. `targets[*].summary`
3. `results[*].status`
4. `results[*].severity`
5. `results[*].message`
6. `fix_hints`, `locations`, and `evidence`

Use `matching` when the failure might be caused by a bad or uncertain entity
match rather than by the rule itself.
