"""
Currency Converter API - Configuration Module
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = BASE_DIR / "exports"
HISTORY_FILE = BASE_DIR / "conversion_history.json"

LOGS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)

API_KEY = os.getenv("EXCHANGE_RATE_API_KEY", "")
BASE_URL = "https://v6.exchangerate-api.com/v6"
FALLBACK_URL = "https://api.exchangerate-api.com/v4/latest"

REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 1

CACHE_DURATION = 3600

LOG_FILE = LOGS_DIR / "currency_converter.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

POPULAR_CURRENCIES = [
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR", "BRL",
    "MXN", "SGD", "HKD", "KRW", "TRY", "ZAR", "NOK", "SEK", "DKK", "PLN"
]

CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CHF": "CHF",
    "CAD": "C$", "AUD": "A$", "CNY": "¥", "INR": "₹", "BRL": "R$",
    "MXN": "MX$", "SGD": "S$", "HKD": "HK$", "KRW": "₩", "TRY": "₺",
    "ZAR": "R", "NOK": "kr", "SEK": "kr", "DKK": "kr", "PLN": "zł"
}

CURRENCY_NAMES = {
    "USD": "US Dollar", "EUR": "Euro", "GBP": "British Pound", "JPY": "Japanese Yen",
    "CHF": "Swiss Franc", "CAD": "Canadian Dollar", "AUD": "Australian Dollar",
    "CNY": "Chinese Yuan", "INR": "Indian Rupee", "BRL": "Brazilian Real",
    "MXN": "Mexican Peso", "SGD": "Singapore Dollar", "HKD": "Hong Kong Dollar",
    "KRW": "South Korean Won", "TRY": "Turkish Lira", "ZAR": "South African Rand",
    "NOK": "Norwegian Krone", "SEK": "Swedish Krona", "DKK": "Danish Krone",
    "PLN": "Polish Zloty"
}

COLORS = {
    "bg": "#1a1a2e",
    "fg": "#eaeaea",
    "accent": "#00d9a5",
    "accent_hover": "#00f5c4",
    "card_bg": "#16213e",
    "border": "#0f3460",
    "success": "#00d9a5",
    "error": "#ff4757",
    "warning": "#ffa502",
    "text_secondary": "#a0a0a0",
    "input_bg": "#16213e",
    "input_fg": "#eaeaea",
    "button_bg": "#0f3460",
    "button_fg": "#eaeaea",
    "button_active": "#00d9a5",
    "table_header": "#16213e",
    "table_row_alt": "#1a1a2e",
    "table_selected": "#0f3460",
}

WINDOW_TITLE = "Currency Converter"
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 700
MIN_WIDTH = 750
MIN_HEIGHT = 600

MAX_HISTORY = 100