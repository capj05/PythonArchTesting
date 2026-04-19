# Testing

This document describes the current testing strategy, structure, and quality gates.

## Test Structure

The suite is centered under `tests/` with layered coverage:

```text
tests/
├── conftest.py
├── test_config_import_boundaries.py
├── test_config_refactor.py
├── test_config_regression.py
├── test_rules_import_safety.py
├── test_rules_refactor_parity.py
├── unit/
├── integration/
├── performance/
├── property/
├── import_safety/
├── fixtures/
└── files/
```

## Running Tests

Common commands:

```bash
# Full suite (project default flags from pytest.ini)
pytest tests/ -v -n auto

# Determinism regression checks
pytest tests/unit/test_parallel_isolation.py -q -k "derive_target_seed_is_stable_across_python_hash_seed or derive_target_seed_differs_by_target_id" -o addopts=''

# Local CI-parity coverage gate
pytest tests/ -v -n auto --cov=pythonarchtesting --cov-fail-under=80
```

## Quality Gates

`check_standard.ps1` runs fail-fast gates in order:

1. `pytest tests/ -v -n auto --cov=pythonarchtesting --cov-fail-under=80`
2. `flake8 src/ tests/`
3. `black --check src/ tests/`
4. `isort --check-only src/ tests/`
5. `mypy src/pythonarchtesting --ignore-missing-imports`
6. `vulture --min-confidence 70 src tests`

`check_full.ps1` runs `check_standard.ps1` first, then extended checks (`radon`,
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

## Mypy Rollout Phases

Phase 0 (bootstrap):

- `src/pythonarchtesting/constants`
- `src/pythonarchtesting/__init__.py`
- `src/pythonarchtesting/exceptions.py`
- `src/pythonarchtesting/run_state.py`

Phase 1 (quick wins):

- `src/pythonarchtesting/cli.py`
- `src/pythonarchtesting/matching`
- `src/pythonarchtesting/execution`
- `src/pythonarchtesting/entities.py`
- `src/pythonarchtesting/entities_extraction`
- `src/pythonarchtesting/runner`
- `src/pythonarchtesting/evidence`
- `src/pythonarchtesting/wrappers`

Phase 2 (foundation modules):

- `src/pythonarchtesting/config`
- `src/pythonarchtesting/util`
- `src/pythonarchtesting/core`
- `src/pythonarchtesting/infrastructure`

Phase 3 (integration):

- `src/pythonarchtesting/runtime`
- `src/pythonarchtesting/report`

Phase 4:

- `src/pythonarchtesting/rules`

Phase 5:

- `src/pythonarchtesting/state`

Phase 6 (convergence):

- Switch the blocking gate back to full `mypy src/ --ignore-missing-imports --show-error-codes --no-incremental`.
- Retire the scoped manifest/script and remove the shadow step.

Enrollment rule per PR:

1. Run `python -m mypy <target> --ignore-missing-imports --follow-imports=skip --show-error-codes --no-incremental`.
2. Fix until the target has zero errors.
3. Re-run `mypy src/pythonarchtesting --ignore-missing-imports`.
4. Ensure the committed mypy gate passes.

## Transitional Notes

- Run execution and parallel execution paths are isolated and do not rely on the
  `ProjectState` singleton constructor path.
- Legacy singleton/config compatibility tests remain to guard deprecated behavior
  until removal in a future minor release.
