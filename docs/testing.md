# Testing

This document describes the current testing strategy, structure, and quality gates.

## Test Structure

The suite is centered under `tests/` with layered coverage:

```text
tests/
├── conftest.py
├── test_rules_import_safety.py
├── unit/
├── integration/
├── performance/
├── property/
├── import_safety/
├── fixtures/
├── files/
└── utils/
```

## Running Tests

Common commands:

```bash
# Full suite (default flags come from [tool.pytest.ini_options] in pyproject.toml)
pytest tests/ -v -n auto

# Local CI-parity coverage gate
pytest tests/ -v -n auto --cov=pythonarchtesting --cov-fail-under=80
```

Tests resolve fixture paths relative to the repository root, so run `pytest` from
there.

## Quality Gates

Two equivalent entry points ship with the repository: `check_standard.ps1` /
`check_full.ps1` for PowerShell and `check_standard.sh` / `check_full.sh` for
POSIX shells. Both variants run the same tools in the same order and stop at the
first failure. They activate `.venv` when it is present and otherwise use the
interpreter already on `PATH`.

`check_standard` runs fail-fast gates in order:

1. `pytest tests/ -v -n auto --cov=pythonarchtesting --cov-fail-under=80`
2. `flake8 src/ tests/`
3. `black --check src/ tests/`
4. `isort --check-only src/ tests/`
5. `mypy src/pythonarchtesting --ignore-missing-imports`
6. `vulture --min-confidence 70 src tests`

`check_full` runs `check_standard` first, then extended checks (`radon`,
`pylint`, `bandit`).

## CI

CI is defined in `.github/workflows/ci.yml`. It runs:

1. A `unit` matrix job on Python `3.10`, `3.11`, and `3.12`
2. `python -m pip install .[dev]` in each job
3. `pytest tests/unit`
4. Import-safety and import-boundary checks:
   `pytest tests/import_safety tests/test_rules_import_safety.py tests/unit/test_import_safety.py tests/unit/test_import_safety_lazy.py`
5. `mypy src/pythonarchtesting`
6. `flake8 src tests`

CI installs from package metadata only. `requirements.txt` and
`requirements-dev.txt` are not used by the workflow.

## Type Checking

`mypy` runs over the whole package and must be clean:

```bash
mypy src/pythonarchtesting
```

The phased, per-module rollout this project used while adopting mypy is
finished; there is no scoped manifest or wrapper script any more. CI runs the
same unscoped command, so a new module is enrolled simply by keeping it free of
errors.
