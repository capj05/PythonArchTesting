"""Helper module used only to create a reachable forbidden import."""

import requests


def touch_requests_dependency() -> str:
    """Return the imported module name so the dependency is reachable."""
    return requests.__name__
