"""Two-hop violation: this module is the one that actually imports ``telnetlib``."""

import telnetlib  # noqa: F401  -- forbidden, reached via helper_clean -> forbidden_lib


def touch() -> None:
    _ = telnetlib
