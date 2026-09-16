"""target_pass_allow_exception -- imports ``warnings`` (in the ``allow`` list)."""

import warnings

from .helper_clean import helper_action


def do_work() -> None:
    warnings.warn("benign", stacklevel=1)
    helper_action()
