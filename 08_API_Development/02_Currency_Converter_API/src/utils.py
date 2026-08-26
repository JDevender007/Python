"""
Currency Converter API - Utility Functions
"""

import re
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from .config import RETRY_DELAY, HISTORY_FILE, MAX_HISTORY, CURRENCY_SYMBOLS, CURRENCY_NAMES
from .logger import logger


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def format_currency(amount: float, currency: str = "USD", decimals: int = 2) -> str:
    """Format amount with currency symbol."""
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    if currency in ["JPY", "KRW"]:
        decimals = 0
    return f"{symbol}{amount:,.{decimals}f}"


def format_number(num: float, decimals: int = 4) -> str:
    """Format number with specified decimals."""
    if num is None:
        return "N/A"
    return f"{num:,.{decimals}f}"


def format_rate(rate: float) -> str:
    """Format exchange rate."""
    if rate >= 1:
        return f"{rate:.4f}"
    elif rate >= 0.01:
        return f"{rate:.6f}"
    else:
        return f"{rate:.8f}"


def format_percentage(value: float) -> str:
    """Format percentage."""
    return f"{value:.2f}%"


def validate_currency_code(code: str) -> bool:
    """Validate ISO 4217 currency code."""
    if not code:
        return False
    code = code.upper().strip()
    pattern = re.compile(r"^[A-Z]{3}$")
    return bool(pattern.match(code))


def validate_amount(amount: str) -> Optional[float]:
    """Validate and parse amount string."""
    if not amount:
        return None
    try:
        # Remove currency symbols and commas
        cleaned = re.sub(r"[^\d\.\-]", "", amount)
        value = float(cleaned)
        if value < 0:
            return None
        return value
    except ValueError:
        return None


def get_currency_symbol(currency: str) -> str:
    """Get currency symbol."""
    return CURRENCY_SYMBOLS.get(currency.upper(), currency.upper())


def get_currency_name(currency: str) -> str:
    """Get currency full name."""
    return CURRENCY_NAMES.get(currency.upper(), currency.upper())


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for retry with exponential backoff."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_retries} attempts failed. Last error: {e}")
            raise last_exception
        return wrapper
    return decorator


def load_history() -> List[Dict]:
    """Load conversion history from file."""
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading history: {e}")
    return []


def save_history(history: List[Dict]) -> bool:
    """Save conversion history to file."""
    try:
        # Keep only last MAX_HISTORY entries
        history = history[-MAX_HISTORY:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving history: {e}")
        return False


def add_to_history(from_currency: str, to_currency: str, amount: float, result: float, rate: float) -> List[Dict]:
    """Add conversion to history."""
    history = load_history()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "amount": amount,
        "result": result,
        "rate": rate
    }
    history.append(entry)
    save_history(history)
    return history


def clear_history() -> bool:
    """Clear conversion history."""
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
        return True
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return False


def safe_get(data: Dict, *keys, default=None) -> Any:
    """Safely get nested dictionary value."""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def timestamp_to_string(timestamp: str) -> str:
    """Convert ISO timestamp to readable string."""
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return timestamp