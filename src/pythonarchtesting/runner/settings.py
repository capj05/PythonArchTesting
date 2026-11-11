"""The config and the sandbox of a run, chosen without the environment.

``resolve_config`` finds the config of a source the same way whatever the
working directory is; ``sandbox_policy`` builds and checks the sandbox of a
dynamic run. Both raise ``InvalidInputError`` for what cannot be used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.config import Config, load_config
from pythonarchtesting.invalid_input import InvalidInputError

CONFIG_FILENAME = ".pythonarchtesting"
DEFAULT_SANDBOX = "bwrap"
DEFAULT_SANDBOX_MEMORY_MB = 1024
ALLOWED_SANDBOXES = ("limits", "bwrap")


def resolve_config(source: Path, config: Optional[str]) -> tuple[Config, str]:
    """Load the config for ``source`` and return it with the applied file path.

    Neither the working directory nor the environment is consulted, so the same
    call gives the same result whatever the caller's launch directory is.
    The second element is ``"defaults"`` when no config file applies.
    """
    config_path: Optional[Path] = None
    if config is not None:
        config_path = Path(config)
        if not config_path.is_absolute():
            raise InvalidInputError(f"config must be an absolute path: {config}")
        if not config_path.is_file():
            raise InvalidInputError(f"config does not exist: {config}")
    else:
        for directory in (source, source.parent):
            candidate = directory / CONFIG_FILENAME
            if candidate.is_file():
                config_path = candidate
                break
    loaded = load_config(
        config_path=str(config_path) if config_path else None,
        discover_from_cwd=False,
    )
    return loaded, str(config_path) if config_path else "defaults"


def sandbox_policy(dynamic: bool, sandbox: Optional[str], memory_mb: int) -> Any:
    """Build and check the sandbox for a dynamic run; None for static runs.
    An unconfined run (``sandbox`` ``"none"``) is refused."""
    if not dynamic:
        if sandbox is not None or memory_mb != DEFAULT_SANDBOX_MEMORY_MB:
            raise InvalidInputError(
                "sandbox and sandbox_memory_mb apply only with dynamic."
            )
        return None
    from pythonarchtesting.dynamic.sandbox import (
        SandboxPolicy,
        SandboxUnavailableError,
        check_available,
    )

    mode = sandbox or DEFAULT_SANDBOX
    if mode == "none":
        raise InvalidInputError(
            "the MCP server refuses an unconfined run: sandbox none"
        )
    if mode not in ALLOWED_SANDBOXES:
        raise InvalidInputError(
            f"sandbox must be one of {', '.join(ALLOWED_SANDBOXES)}: {mode}"
        )
    if memory_mb <= 0:
        raise InvalidInputError("sandbox_memory_mb must be positive.")
    policy = SandboxPolicy(mode=mode, memory_mb=memory_mb)
    try:
        check_available(policy)
    except SandboxUnavailableError as exc:
        raise InvalidInputError(f"sandbox {mode} is not available here: {exc}") from exc
    return policy


__all__ = [
    "ALLOWED_SANDBOXES",
    "CONFIG_FILENAME",
    "DEFAULT_SANDBOX",
    "DEFAULT_SANDBOX_MEMORY_MB",
    "resolve_config",
    "sandbox_policy",
]
