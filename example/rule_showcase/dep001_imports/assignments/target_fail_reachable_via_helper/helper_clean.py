"""Helper that violates the policy by importing ``telnetlib`` directly."""

import telnetlib  # noqa: F401  -- forbidden via reachable graph


def helper_action() -> str:
    _ = telnetlib
    return "ok"
