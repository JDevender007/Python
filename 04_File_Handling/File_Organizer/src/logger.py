import logging
from config import LOG_FOLDER

LOG_FOLDER.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_FOLDER / "organizer.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)