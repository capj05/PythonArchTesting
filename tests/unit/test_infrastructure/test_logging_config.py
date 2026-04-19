from __future__ import annotations

import logging

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.infrastructure.logging import configure_logging, get_logger


def _flush_handlers() -> None:
    for handler in logging.getLogger().handlers:
        handler.flush()


def test_module_logger_writes_to_configured_file(monkeypatch, tmp_path):
    cfg = create_config_from_dict(
        {"logging": {"level": "INFO", "file": "true", "filename": "module.log"}}
    )
    monkeypatch.chdir(tmp_path)

    configure_logging(cfg, force=True)
    logger = get_logger("pythonarchtesting.runner")
    logger.info("module log line")
    _flush_handlers()

    content = (tmp_path / "module.log").read_text(encoding="utf-8")
    assert "module log line" in content


def test_logging_file_disabled_does_not_create_log_file(monkeypatch, tmp_path):
    cfg = create_config_from_dict(
        {"logging": {"level": "INFO", "file": "false", "filename": "disabled.log"}}
    )
    monkeypatch.chdir(tmp_path)

    configure_logging(cfg, force=True)
    logger = get_logger("pythonarchtesting.runner")
    logger.info("should not be persisted")
    _flush_handlers()

    assert not (tmp_path / "disabled.log").exists()


def test_force_reconfiguration_switches_log_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    cfg1 = create_config_from_dict(
        {"logging": {"level": "INFO", "file": "true", "filename": "one.log"}}
    )
    cfg2 = create_config_from_dict(
        {"logging": {"level": "INFO", "file": "true", "filename": "two.log"}}
    )

    configure_logging(cfg1, force=True)
    logger = get_logger("pythonarchtesting.runner")
    logger.info("first file")
    _flush_handlers()

    configure_logging(cfg2, force=True)
    logger.info("second file")
    _flush_handlers()

    content = (tmp_path / "two.log").read_text(encoding="utf-8")
    assert "second file" in content
