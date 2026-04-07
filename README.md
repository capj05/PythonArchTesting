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

CLI entrypoints:

- `python-arch-test` for most users
- `python -m src.cli` when working from a source checkout during development

## Quick Example

Reference declarations:

```python
from typing import Annotated
from src.rules import forbid_imports, required_entity_signature

__archtest__: Annotated[
    None,
    forbid_imports("statistics", scope="package", package="data_processor"),
]


def normalize(
    value: str,
) -> Annotated[
    str,
    required_entity_signature(mode="compatible", return_annotation="warning"),
]:
    return value.strip().lower()
```

Validate the reference declarations before comparing targets:

```bash
python-arch-test --validate-declarations --source example/project_1/reference --format json
```

Analyze a batch of targets and print a JSON report:

```bash
python-arch-test --source example/project_1/reference --targets-dir example/project_1/assignments --format json
```

Generate a Markdown bundle for the same run:

```bash
python-arch-test --source example/project_1/reference --targets-dir example/project_1/assignments --format markdown --output reports/project_1_markdown
```

## How To Interpret Results

Read reports in this order:

1. `exit_code` and `summary`
2. `targets[*].summary` for multi-target runs
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
