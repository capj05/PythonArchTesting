from __future__ import annotations

import logging
from typing import Any

from src.config.accessors import get_bool, get_str

FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"
FORMATTER_NAME = "default"
DEFAULT_OUTPUT_FILE = "log.txt"
LOGGER_NAME = "shared_logger"
DEFAULT_LOGGER_LEVEL = "DEBUG"


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def configure_logging(config: Any, force: bool = False) -> None:
    """
    Configure logging handlers using config values.

    Call this explicitly after configuration is loaded.

    Args:
        config: Configuration object with get_str and get_boolean methods
        force: Force reconfiguration even if handlers already exist
    """
    root_logger = logging.getLogger()

    if root_logger.handlers and not force:
        return
    if force:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

    level = get_str(config, "logging", "level", DEFAULT_LOGGER_LEVEL)
    root_logger.setLevel(level)

    file_enabled = get_bool(config, "logging", "file", True)
    if file_enabled is False:
        if not root_logger.handlers:
            root_logger.addHandler(logging.NullHandler())
        return

    output_file = get_str(config, "logging", "filename", DEFAULT_OUTPUT_FILE)
    file_handler = logging.FileHandler(output_file, mode="w", encoding="utf-8")
    file_handler.setLevel(level)
    formatter = logging.Formatter(fmt=FORMAT, datefmt=DATEFMT)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Keep the shared logger available for compatibility while inheriting root
    # setup.
    shared_logger = logging.getLogger(LOGGER_NAME)
    shared_logger.propagate = True
