"""Application logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "pathfinding_visualizer"
_CONFIGURED = False


def configure_logging() -> logging.Logger:
    """Configure console and rotating-file logging exactly once."""
    global _CONFIGURED
    logger = logging.getLogger(_LOGGER_NAME)
    if _CONFIGURED:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        project_root = Path(__file__).resolve().parent.parent
        log_directory = project_root / "logs"
        log_directory.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_directory / "pathfinding_visualizer.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("File logging is unavailable; console logging remains active.")

    _CONFIGURED = True
    return logger


def get_logger(module_name: str) -> logging.Logger:
    """Return a child logger for ``module_name``."""
    base_logger = configure_logging()
    return base_logger.getChild(module_name)
