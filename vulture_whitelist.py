"""Vulture whitelist.

Names vulture reports as unused variables that are in fact required parameters.
Passed to vulture by the quality gates:

    vulture --min-confidence 70 src tests vulture_whitelist.py

Keep every entry justified; an unexplained entry hides real dead code.
"""

# Parameters of test stubs that must mirror the real callee signature.
fmt  # noqa: F821  # tests/unit/test_cli/test_run_formats.py:132,186
