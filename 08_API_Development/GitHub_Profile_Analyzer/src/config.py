"""
GitHub Profile Analyzer - Configuration Module
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

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
BASE_URL = "https://api.github.com"

REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 1

CACHE_DURATION = 300

LOG_FILE = LOGS_DIR / "github_analyzer.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

DEFAULT_PER_PAGE = 30
MAX_REPOS_PER_USER = 1000

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
    "input_bg": "#161b22",
    "input_fg": "#e6edf3",
    "button_bg": "#21262d",
    "button_fg": "#e6edf3",
    "button_active": "#58a6ff",
    "table_header": "#161b22",
    "table_row_alt": "#0d1117",
    "table_selected": "#1f3a5f",
    "lang_python": "#3572A5",
    "lang_javascript": "#f1e05a",
    "lang_typescript": "#3178C6",
    "lang_java": "#b07219",
    "lang_cpp": "#f34b7d",
    "lang_cs": "#239120",
    "lang_go": "#00ADD8",
    "lang_rust": "#dea584",
    "lang_php": "#4F5D95",
    "lang_ruby": "#701516",
}

WINDOW_TITLE = "GitHub Profile Analyzer"
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 800
MIN_WIDTH = 900
MIN_HEIGHT = 650

GITHUB_GREEN = "#3fb950"
GITHUB_BLUE = "#58a6ff"
GITHUB_PURPLE = "#a371f7"
GITHUB_ORANGE = "#d29922"
GITHUB_RED = "#f85149"