"""The error the core raises for a request it refuses.

A core function (``runner.settings``, ``report.load``, ``verification``,
``principles.task_verification``) raises ``InvalidInputError`` when what it
was given cannot be used: a config path that is not absolute, a sandbox that
is not available, a reference with no rule of the name asked for. The message
says why and what to give instead; a caller with a user (the MCP layer) passes
it on unchanged.
"""

from __future__ import annotations


class InvalidInputError(ValueError):
    """A request the core refuses; the message is meant for its user."""


__all__ = ["InvalidInputError"]
