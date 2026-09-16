"""target_pass_ignore_globs -- reaches ``telnetlib`` only via a glob-excluded module."""

from .helper_clean import helper_action
from .ignored_module import noop  # noqa: F401  -- glob-excluded module


def do_work() -> None:
    noop()
    helper_action()
