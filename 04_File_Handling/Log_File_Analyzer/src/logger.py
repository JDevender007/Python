import logging

from config import APP_LOG_FOLDER

APP_LOG_FOLDER.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=APP_LOG_FOLDER / "application.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)