from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
EXPORT_DIR = BASE_DIR / "exports"

DATABASE_FILE = DATA_DIR / "tracker.db"
LOG_FILE = LOG_DIR / "price_tracker.log"

APP_NAME = "Amazon Price Tracker"
APP_VERSION = "1.0.0"

WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900

MIN_WIDTH = 1100
MIN_HEIGHT = 700

FONT_FAMILY = "Segoe UI"

TITLE_SIZE = 26
HEADING_SIZE = 18
SUBHEADING_SIZE = 14
BODY_SIZE = 12
SMALL_SIZE = 10

REQUEST_TIMEOUT = 20

MAX_PRODUCTS = 500

DEFAULT_TARGET_PRICE = 0.0

CURRENCY_SYMBOL = "₹"

DATE_FORMAT = "%d %b %Y, %I:%M %p"

PRICE_CHECK_INTERVAL = 3600

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

EXPORT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)
