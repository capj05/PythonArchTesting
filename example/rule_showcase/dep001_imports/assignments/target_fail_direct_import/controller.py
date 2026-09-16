"""target_fail_direct_import -- controller imports ``telnetlib`` directly."""

import telnetlib  # noqa: F401  -- forbidden!

from .helper_clean import helper_action


def do_work() -> None:
    _ = telnetlib
    helper_action()
