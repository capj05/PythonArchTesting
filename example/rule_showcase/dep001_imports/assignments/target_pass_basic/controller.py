"""target_pass_basic -- clean controller, clean helper, no forbidden imports."""

from .helper_clean import helper_action


def do_work() -> None:
    helper_action()
