from pathlib import Path
import logging


LOG_DIR = Path("logs")

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LOG_FILE = LOG_DIR / "job_scraper.log"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)


logger = logging.getLogger(
    "Job_Listing_Scraper"
)