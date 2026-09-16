"""Helper -- doesn't import telnetlib itself, but pulls in forbidden_lib."""

from .forbidden_lib import touch


def helper_action() -> str:
    touch()
    return "ok"
