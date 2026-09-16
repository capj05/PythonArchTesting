"""Vulture whitelist.

Names vulture reports as unused variables that are in fact required parameters.
Passed to vulture by the quality gates:

    vulture --min-confidence 70 src tests vulture_whitelist.py

Keep every entry justified; an unexplained entry hides real dead code.
"""

# Keyword-only parameter of the public register_sink() extension point.
# Downstream integrations pass it by name, so it must stay in the signature.
optional_extra  # noqa: F821  # src/pythonarchtesting/report/dispatcher.py:48

# Parameter of IRGenerator.generate() in a typing.Protocol. Protocol method
# signatures declare parameters without using them.
options  # noqa: F821  # src/pythonarchtesting/report/renderers/protocol.py:26

# Parameters of test stubs that must mirror the real callee signature.
fmt  # noqa: F821  # tests/unit/test_cli/test_run_formats.py:132,186
