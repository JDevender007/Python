"""Logging configuration for Stack Queue Simulator."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOGGER_NAME = "stack_queue_simulator"


def configure_logging() -> logging.Logger:
    """Configure and return the application logger.

    The function is idempotent, so importing and calling it from multiple
    modules does not create duplicate handlers.
    """

    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    try:
        project_root = Path(__file__).resolve().parents[1]
        log_directory = project_root / "logs"
        log_directory.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_directory / "simulator.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as exc:
        logger.warning("File logging is unavailable: %s", exc)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the application logger or a named child logger."""

    root_logger = configure_logging()
    return root_logger if not name else root_logger.getChild(name)
