#!/usr/bin/env bash
# Full quality gates. POSIX counterpart of check_full.ps1: runs the standard
# gates first, then the extended ones.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

echo "Running full checks..."
"$script_dir/check_standard.sh"

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

run_gate radon radon cc -nc src/ tests/
run_gate pylint pylint --disable=all --enable=R0912,R0915 src/
run_gate bandit bandit -r src/
echo "Full checks completed."
