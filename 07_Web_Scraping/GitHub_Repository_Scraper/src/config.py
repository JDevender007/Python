"""
GitHub Repository Scraper - Configuration Module
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = BASE_DIR / "exports"

LOGS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)

DEFAULT_URL = "https://github.com/trending"

REQUEST_TIMEOUT = 15
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

CSV_FILENAME = "github_repos.csv"
JSON_FILENAME = "github_repos.json"

LOG_FILE = LOGS_DIR / "github_scraper.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

MAX_REPOS = 100

COLORS = {
    "bg": "#0d1117",
    "fg": "#e6edf3",
    "accent": "#58a6ff",
    "accent_hover": "#79b8ff",
    "card_bg": "#161b22",
    "border": "#30363d",
    "success": "#3fb950",
    "error": "#f85149",
    "warning": "#d29922",
    "text_secondary": "#8b949e",
    "green": "#3fb950",
    "purple": "#a371f7",
}

WINDOW_TITLE = "GitHub Repository Scraper"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
MIN_WIDTH = 1000
MIN_HEIGHT = 700