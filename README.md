# PythonArchTesting

PythonArchTesting compares one or more target Python projects against a
reference project that declares architectural expectations in code. The tool
reads passive `Annotated[...]` metadata from the reference project, matches
source entities to target entities, and reports where each target satisfies or
violates the declared rules.

The CLI is purely static: it parses source files and annotation metadata and
does not execute application code to decide whether a rule passed.

## What It Can Check

All markers are imported from `pythonarchtesting.rules`. See
[docs/api-reference.md](docs/api-reference.md) for the full option surface and
[docs/pattern-recipes.md](docs/pattern-recipes.md) for ready-to-use combinations.

**Signature and shape**

- `required_entity_signature` — required signature for a function or method
- `required_method` — required method on a class with a compatible signature
- `require_method_set` — set of required methods declared at class level
- `require_member_set` — set of required attributes declared at class level
- `required_constructor` — required `__init__` shape
- `required_factory` — required factory classmethod or function shape
- `required_attribute` — required instance or class attribute
- `does_not_have` — explicitly forbid a member by name

**Imports**

- `forbid_imports` — module-scoped or package-scoped import policy, in either
  direct AST mode or graph (reachable-import) mode

**Type identity and inheritance**

- `implements_protocol` — structural protocol conformance
- `subclass_of`, `not_subclass_of`, `inherits_directly_from`, `exact_type` —
  inheritance and identity checks
- `is_enum` — class must be an `Enum` subclass

**Abstractness and finality**

- `is_abstract_class`, `is_concrete_class`, `is_final_class`,
  `is_non_final_class` — class-level modifiers
- `is_abstract_method`, `is_non_abstract_method`, `is_final_method`,
  `is_non_final_method` — method-level modifiers

**Variable flow**

- `flow` — mark a statement as a stage in an ordered variable flow
- `enforce_flow` — require those stages to appear in declared order

At the report level these markers map to four evaluator families:
`api_signature`, `import_policy`, `protocol_conformance`, and `variable_flow`.

A separate CLI mode validates the reference declarations themselves before any
target is analyzed:

```bash
python-arch-test --validate-declarations --source <reference_path>
```

## Core Concepts

- **Reference project** — the source of truth that contains rule declarations.
- **Target project** — the codebase being checked against the reference.
- **Declarations** — passive `Annotated[...]` metadata read by the CLI; not
  executed at import time.
- **Reports** — JSON or Markdown output describing matching, rule results, and
  exit status.

## Install

Standard install:

```bash
pip install .
```

Editable development install with test and lint extras:

```bash
pip install -e .[dev]
```

Dependencies are declared in `pyproject.toml` only. The repository does not
maintain `requirements*.txt` files.

CLI entrypoints:

- `python-arch-test` — installed console script
- `python -m pythonarchtesting.cli` — direct invocation from a source checkout

## Quick Example

The repository ships a canonical worked example at `example/checkout_assignment/`.
The snippets and CLI commands below are drawn from it — every path is a real
file you can open in the tree.

Module-level import policy (forbids HTTP libraries inside the storage package):

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

Class-level cluster declaring required attributes and a compatible constructor
signature:

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
subtrees. `scope="entity"` remains a compatibility alias for `module`. Bare
`forbid_imports(...)` uses graph-based reachable-import checking by default;
pass `mode="direct"` for the direct AST import check.

## Run It

Validate the reference declarations on their own:

```bash
python-arch-test --validate-declarations \
    --source example/checkout_assignment/reference
```

Analyze a single target:

```bash
python-arch-test \
    --source example/checkout_assignment/reference \
    --target example/checkout_assignment/assignments/target1 \
    --format json
```

Analyze a directory of targets and emit JSON:

```bash
python-arch-test \
    --source example/checkout_assignment/reference \
    --targets-dir example/checkout_assignment/assignments \
    --format json
```

Generate a Markdown bundle for the same run:

```bash
python-arch-test \
    --source example/checkout_assignment/reference \
    --targets-dir example/checkout_assignment/assignments \
    --format markdown \
    --output example/checkout_assignment/reports/report_md
```

Pre-rendered reports for this example live at
`example/checkout_assignment/reports/`.

## How To Read A Report

Read the JSON output in this order:

1. `exit_code` and the top-level `summary`
2. `targets[*].summary` for run reports
3. `results[*].status`, `results[*].severity`, and `results[*].message`
4. `fix_hints`, `locations`, and `evidence` for remediation details

Matching data explains whether a source entity was confidently paired with a
target entity. The four matching states are `matched`, `low_confidence`,
`ambiguous`, and `unmatched`. See [docs/reporting.md](docs/reporting.md) for the
full output reference.

## Where To Go Next

- [Documentation index](docs/README.md)
- [Overview](docs/overview.md) — concepts and supported checks
- [Usage guide](docs/usage-guide.md) — step-by-step worked example
- [Configuration](docs/configuration.md) — `.pythonarchtesting` reference
- [API reference](docs/api-reference.md) — every marker and option
- [Per-marker reference](docs/markers/README.md) — focused page per marker
- [Pattern recipes](docs/pattern-recipes.md) — common-pattern declarations
- [Reporting](docs/reporting.md) — output formats and exit codes
- [Architecture](docs/architecture.md) — pipeline and module map
