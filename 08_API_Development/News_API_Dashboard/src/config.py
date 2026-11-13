"""
News API Dashboard - Configuration Module
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = BASE_DIR / "exports"

LOGS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
BASE_URL = "https://newsapi.org/v2"

REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1

CACHE_DURATION = 600

LOG_FILE = LOGS_DIR / "news_dashboard.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

DEFAULT_COUNTRY = "us"
DEFAULT_CATEGORY = "general"
DEFAULT_PAGE_SIZE = 20

COUNTRIES = {
    "us": "United States",
    "gb": "United Kingdom",
    "ca": "Canada",
    "au": "Australia",
    "de": "Germany",
    "fr": "France",
    "jp": "Japan",
    "in": "India",
    "br": "Brazil",
    "mx": "Mexico",
    "it": "Italy",
    "es": "Spain",
    "nl": "Netherlands",
    "se": "Sweden",
    "ch": "Switzerland",
    "no": "Norway",
    "dk": "Denmark",
    "fi": "Finland",
    "pl": "Poland",
}

CATEGORIES = [
    "general", "business", "entertainment", "health",
    "science", "sports", "technology"
]

SORT_OPTIONS = ["publishedAt", "relevancy", "popularity"]

COLORS = {
    "bg": "#0f172a",
    "fg": "#f1f5f9",
    "accent": "#38bdf8",
    "accent_hover": "#7dd3fc",
    "card_bg": "#1e293b",
    "border": "#334155",
    "success": "#22c55e",
    "error": "#ef4444",
    "warning": "#f59e0b",
    "text_secondary": "#94a3b8",
    "input_bg": "#1e293b",
    "input_fg": "#f1f5f9",
    "button_bg": "#1e293b",
    "button_fg": "#f1f5f9",
    "button_active": "#38bdf8",
    "table_header": "#1e293b",
    "table_row_alt": "#0f172a",
    "table_selected": "#1e3a5f",
    "category_bg": "#1e293b",
    "category_border": "#334155",
}

WINDOW_TITLE = "News API Dashboard"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 850
MIN_WIDTH = 950
MIN_HEIGHT = 700

MAX_ARTICLES_CACHE = 500