"""Glob-excluded helper -- imports ``telnetlib`` deliberately.

Matched by ``ignore_globs=("**/ignored_module.py",)`` so the rule must
ignore the import even though it is reachable from the controller.
"""

import telnetlib  # noqa: F401  -- intentional, glob-excluded


def noop() -> None:
    _ = telnetlib
