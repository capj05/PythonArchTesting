#!/usr/bin/env bash
# Standard quality gates. POSIX counterpart of check_standard.ps1; both run the
# same tools in the same order and stop at the first failure.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    . .venv/bin/activate
fi
export PYTHONPATH="$script_dir/src"

run_gate() {
    name="$1"
    shift
    echo "Running $name..."
    "$@"
}

echo "Running standard checks..."
run_gate pytest pytest tests/ -v -n auto --cov=pythonarchtesting --cov-fail-under=80
run_gate flake8 flake8 src/ tests/
run_gate black black --check src/ tests/
run_gate isort isort --check-only src/ tests/
run_gate mypy python -m mypy src/pythonarchtesting --ignore-missing-imports
run_gate vulture vulture --min-confidence 70 src tests vulture_whitelist.py
echo "Standard checks completed."
