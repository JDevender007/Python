"""Application logging configuration."""

import logging
from logging.handlers import RotatingFileHandler

from .config import APP_NAME, LOG_FILE


def configure_logging() -> logging.Logger:
    """Configure and return the application logger.

    The function is idempotent so importing the application repeatedly does not
    duplicate log handlers.
    """

    logger = logging.getLogger(APP_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("File logging could not be initialized", exc_info=True)

    logger.propagate = False
    return logger


LOGGER = configure_logging()
