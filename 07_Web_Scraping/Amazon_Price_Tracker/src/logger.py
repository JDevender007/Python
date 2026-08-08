import logging

from src.config import LOG_FILE


logger = logging.getLogger("AmazonPriceTracker")

logger.setLevel(logging.INFO)

if not logger.handlers:

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8",
    )

    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
