# Usage Guide

This guide walks through the normal user flow:

1. write declarations in the reference project
2. validate those declarations
3. run one target or many targets
4. read the report in the right order

For most users, install the package and use `python-arch-test`. The
`python -m pythonarchtesting.cli` entrypoint is mainly useful when working from a source
checkout during development.

## 1. Write Reference Declarations

Example reference code:

```python
from typing import Annotated
from pythonarchtesting.rules import forbid_imports, required_entity_signature, required_method

__archtest__: Annotated[
    None,
    forbid_imports(
        "statistics",
        scope="package",
        package="data_processor",
        mode="direct",
    ),
]


def normalize_operands(
    a: float,
    b: float = 0.0,
) -> Annotated[
    tuple[float, float],
    required_entity_signature(mode="compatible"),
]:
    return (float(a), float(b))


class Calculator:
    def add(self, a: float, b: float) -> float:
        __archtest__: Annotated[None, required_method(signature_mode="compatible")]
        return a + b
```

`forbid_imports(...)` uses `scope="module"` for file-wide checks and
`scope="package"` for package-subtree checks. The legacy `scope="entity"`
spelling is still accepted for compatibility, but `module` is the canonical
public name. Bare `forbid_imports(...)` defaults to reachable mode; use
`mode="direct"` when you want the direct AST import check instead.

Other supported declaration shapes:

```python
from typing import Annotated
from pythonarchtesting.rules import enforce_flow, flow, implements_protocol


class RepositoryAdapter:
    __archtest__: Annotated[None, implements_protocol("reference.Repository")]


def build(repo: Annotated[object, implements_protocol("reference.Repository")]) -> None:
    value = repo
    __archtest__: Annotated[None, flow("raw", variable="value")]
    value = repo
    __archtest__: Annotated[None, flow("validated", variable="value")]
    __archtest__: Annotated[
        None,
        enforce_flow(["raw", "validated"], variable="value"),
    ]
```

## 2. Validate Declarations First

Use declaration validation to catch invalid metadata before comparing targets:

```bash
python-arch-test --validate-declarations --source path/to/reference --format json
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
python-arch-test --source path/to/reference --target path/to/assignments/target1 --format json
```

## 4. Run Multiple Targets

Batch analysis from a directory:

```bash
python-arch-test --source path/to/reference --targets-dir path/to/assignments --format json
```

Explicit target list:

```bash
python-arch-test --source path/to/reference --target path/to/target_a --target path/to/target_b --format json
```

Target discovery controls:

- `--targets-dir` scans subdirectories
- `--project-pattern` filters those subdirectories
- `--exclude-patterns` removes unwanted matches

## 5. Generate A Markdown Bundle

Markdown output always requires `--output` pointing to a directory, whether you
are running one target or many:

```bash
python-arch-test --source path/to/reference --targets-dir path/to/assignments --format markdown --output reports/project_markdown
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
python-arch-test --validate-declarations --source path/to/reference --validation-scope all --format json
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
