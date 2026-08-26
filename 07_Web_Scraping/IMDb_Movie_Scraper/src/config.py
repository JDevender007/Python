"""
IMDb Movie Scraper - Configuration Module
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = BASE_DIR / "exports"

LOGS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)

DEFAULT_URL = "https://www.imdb.com/chart/top/"

REQUEST_TIMEOUT = 10
REQUEST_DELAY = 2

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

CSV_FILENAME = "imdb_movies.csv"
JSON_FILENAME = "imdb_movies.json"

LOG_FILE = LOGS_DIR / "imdb_scraper.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

MAX_MOVIES = 250

COLORS = {
    "bg": "#1e1e1e",
    "fg": "#ffffff",
    "accent": "#f5c518",
    "accent_hover": "#ffd700",
    "card_bg": "#2d2d2d",
    "border": "#3d3d3d",
    "success": "#4caf50",
    "error": "#f44336",
    "warning": "#ff9800",
    "text_secondary": "#b0b0b0",
}

WINDOW_TITLE = "IMDb Movie Scraper"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
MIN_WIDTH = 1000
MIN_HEIGHT = 700