"""Reference settings for the DYN005 runtime member showcase.

``Settings`` fills its fields from a dict of defaults in a loop, so the
attribute names never appear in the source as ``self.host = ...``. Static
attribute rules cannot see them; the runtime markers build an instance and
look at it.

- ``require_runtime_members``: every instance has ``host``, ``port`` and
  ``debug``.
- ``forbid_runtime_members``: no instance keeps the ``password`` it was given:
  secrets are passed to the connection, never stored on the settings object.
"""

from __future__ import annotations

from typing import Annotated, Any

from pythonarchtesting.rules import forbid_runtime_members, require_runtime_members

DEFAULTS: dict[str, Any] = {"host": "localhost", "port": 5432, "debug": False}


class Settings:
    __archtest__: Annotated[
        None,
        require_runtime_members(
            "host",
            "port",
            "debug",
            cases=[{"args": [{}]}, {"args": [{"port": 6543, "password": "s3cret"}]}],
        ),
        forbid_runtime_members(
            "password",
            cases=[{"args": [{"port": 6543, "password": "s3cret"}]}],
        ),
    ]

    def __init__(self, overrides: dict[str, Any]) -> None:
        values = {**DEFAULTS, **overrides}
        for key in DEFAULTS:
            setattr(self, key, values[key])
