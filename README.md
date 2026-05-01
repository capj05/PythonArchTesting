# PythonArchTesting

PythonArchTesting compares one or more target Python projects against a
reference project that declares architectural expectations in code. The tool
reads passive annotations from the reference project, matches source entities to
target entities, and reports where a target satisfies or violates those rules.

## What It Can Check

- Required function signatures with `required_entity_signature`
- Required methods with `required_method`
- Forbidden imports with `forbid_imports`
- Protocol conformance with `implements_protocol`
- Ordered variable-flow checks with `flow` and `enforce_flow`
- Reference declaration validity with `--validate-declarations`

## Core Concepts

- Reference project: the source of truth that contains rule declarations
- Target project: the codebase being checked against the reference project
- Declarations: passive `Annotated[...]` metadata read by the CLI, not executed
  at import time
- Reports: JSON or Markdown output that summarizes matching, rule results, and
  exit status

## Install And Run

Install the package for normal use:

```bash
pip install .
```

Editable development install:

```bash
pip install -e .[dev]
```

Dependency declarations are maintained only in `pyproject.toml`. Do not add or
edit `requirements*.txt` files in this repository.

CLI entrypoints:

- `python-arch-test` for most users
- `python -m pythonarchtesting.cli` when working from a source checkout during development

## Quick Example

The repository ships a canonical worked example at
`example/checkout_assignment/`. The snippets and CLI commands below are drawn
from it — every path is a real file you can open in the tree.

Module-level import policy (forbids HTTP libraries inside the storage
package):

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

Class-level cluster declaring required attributes and a compatible
constructor signature:

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

Use `scope="module"` for file-wide checks and `scope="package"` for package
subtrees. `scope="entity"` remains a compatibility alias for `module`.
Bare `forbid_imports(...)` uses graph-based reachable-import checking by
default; use `mode="direct"` for the direct AST import check.

Validate the reference declarations before comparing targets:

```bash
python-arch-test --validate-declarations --source example/checkout_assignment/reference --format json
```

Analyze a batch of targets and print a JSON report:

```bash
python-arch-test --source example/checkout_assignment/reference --targets-dir example/checkout_assignment/assignments --format json
```

Generate a Markdown bundle for the same run:

```bash
python-arch-test --source example/checkout_assignment/reference --targets-dir example/checkout_assignment/assignments --format markdown --output example/checkout_assignment/reports/report_md
```

Pre-rendered reports for this example live at
`example/checkout_assignment/reports/`.

## How To Interpret Results

Read reports in this order:

1. `exit_code` and `summary`
2. `targets[*].summary` for run reports
3. `results[*].status`, `results[*].severity`, and `results[*].message`
4. `fix_hints`, `locations`, and `evidence` for remediation details

Matching data explains whether a source entity was confidently paired with a
target entity. The main matching states are `matched`, `low_confidence`,
`ambiguous`, and `unmatched`.

## Where To Go Next

- [Documentation index](docs/README.md)
- [Overview](docs/overview.md)
- [Usage guide](docs/usage-guide.md)
- [Configuration](docs/configuration.md)
- [Reporting](docs/reporting.md)
- [Architecture](docs/architecture.md)
- [API reference](docs/api-reference.md)
