"""
Weather API Client - Configuration Module
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

API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
BASE_URL = "https://api.openweathermap.org/data/2.5"
GEO_URL = "https://api.openweathermap.org/geo/1.0"

REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 1

DEFAULT_UNITS = "metric"
DEFAULT_LANG = "en"

LOG_FILE = LOGS_DIR / "weather_client.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

CACHE_DURATION = 300

COLORS = {
    "bg": "#1e1e2e",
    "fg": "#cdd6f4",
    "accent": "#89b4fa",
    "accent_hover": "#b4befe",
    "card_bg": "#313244",
    "border": "#45475a",
    "success": "#a6e3a1",
    "error": "#f38ba8",
    "warning": "#f9e2af",
    "text_secondary": "#a6adc8",
    "temp_cold": "#89b4fa",
    "temp_cool": "#b4befe",
    "temp_mild": "#f9e2af",
    "temp_warm": "#fab387",
    "temp_hot": "#f38ba8",
}

WINDOW_TITLE = "Weather API Client"
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
MIN_WIDTH = 800
MIN_HEIGHT = 600

POPULAR_CITIES = [
    "London,UK", "New York,US", "Tokyo,JP", "Paris,FR", "Sydney,AU",
    "Dubai,AE", "Singapore,SG", "Hong Kong,HK", "Toronto,CA", "Berlin,DE",
    "Mumbai,IN", "São Paulo,BR", "Moscow,RU", "Seoul,KR", "Amsterdam,NL"
]