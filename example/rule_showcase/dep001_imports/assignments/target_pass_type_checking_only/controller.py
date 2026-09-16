"""target_pass_type_checking_only -- ``telnetlib`` only under TYPE_CHECKING."""

from typing import TYPE_CHECKING

from .helper_clean import helper_action

if TYPE_CHECKING:
    import telnetlib  # noqa: F401  -- ignored by ignore_type_checking=True


def do_work() -> None:
    helper_action()
