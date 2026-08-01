"""Application logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "graph_traversal_visualizer"


def configure_logging() -> logging.Logger:
    """Configure console and rotating-file logging once."""
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        log_directory = Path.home() / ".graph_traversal_visualizer"
        log_directory.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_directory / "application.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("File logging is unavailable; console logging remains active.")

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the application namespace."""
    root_logger = configure_logging()
    return root_logger.getChild(name)
