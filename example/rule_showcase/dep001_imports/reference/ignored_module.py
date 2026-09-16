"""Glob-excluded helper -- imports ``telnetlib`` deliberately.

This module is matched by the ``ignore_globs`` pattern declared in
``controller.py`` (``**/ignored_module.py``). The ``forbid_imports`` rule
must therefore ignore the import below even though it would otherwise be
reachable from the controller in graph mode.
"""

import telnetlib  # noqa: F401  -- intentional, glob-excluded


def noop() -> None:
    """Touch the import so linters do not strip it."""
    _ = telnetlib
