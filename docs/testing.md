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
pytest tests/ -v -n auto --cov=src --cov-fail-under=80
```

## Quality Gates

`check_standard.ps1` runs fail-fast gates in order:

1. `pytest tests/ -v -n auto --cov=src --cov-fail-under=80`
2. `flake8 src/ tests/`
3. `black --check src/ tests/`
4. `isort --check-only src/ tests/`
5. `python scripts/mypy_scoped_gate.py --targets-file configs/mypy_rollout_targets.txt`
6. `vulture --min-confidence 70 src tests`

`check_full.ps1` runs `check_standard.ps1` first, then extended checks (`radon`,
`pylint`, `bandit`).

## CI

CI is defined in `.github/workflows/ci.yml`. It runs:

1. `pytest tests/ -v -n auto --cov=src --cov-fail-under=80`
2. `python tools/diagrams/check_freshness.py --profile ci`
3. `flake8 src/ tests/`
4. `black --check src/ tests/`
5. `isort --check-only src/ tests/`
6. `python scripts/mypy_scoped_gate.py --targets-file configs/mypy_rollout_targets.txt`
7. `python -m mypy src/ --ignore-missing-imports --show-error-codes --no-incremental` (non-blocking visibility step during rollout)

## Mypy Rollout Phases

Phase 0 (bootstrap):

- `src/constants`
- `src/__init__.py`
- `src/exceptions.py`
- `src/state_multi.py`

Phase 1 (quick wins):

- `src/cli.py`
- `src/matching`
- `src/execution`
- `src/entities.py`
- `src/entities_extraction`
- `src/runner_multi`
- `src/evidence`
- `src/wrappers`

Phase 2 (foundation modules):

- `src/config`
- `src/util`
- `src/core`
- `src/infrastructure`

Phase 3 (integration):

- `src/runtime`
- `src/report`

Phase 4:

- `src/rules`

Phase 5:

- `src/state`

Phase 6 (convergence):

- Switch the blocking gate back to full `mypy src/ --ignore-missing-imports --show-error-codes --no-incremental`.
- Retire the scoped manifest/script and remove the shadow step.

Enrollment rule per PR:

1. Run `python -m mypy <target> --ignore-missing-imports --follow-imports=skip --show-error-codes --no-incremental`.
2. Fix until the target has zero errors.
3. Add the target to `configs/mypy_rollout_targets.txt`.
4. Ensure scoped gate passes and full shadow step still runs.

## Transitional Notes

- Multi-target and parallel execution paths are isolated and do not rely on the
  `ProjectState` singleton constructor path.
- Legacy singleton/config compatibility tests remain to guard deprecated behavior
  until removal in a future minor release.
