"""
IMDb Movie Scraper - Utility Functions
"""

import re
import time
from typing import Optional
from .config import REQUEST_DELAY
from .logger import logger


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_year(text: str) -> Optional[int]:
    """Extract year from text like '(2023)' or '2023'."""
    if not text:
        return None
    match = re.search(r"\(?(\d{4})\)?", text)
    if match:
        year = int(match.group(1))
        if 1900 <= year <= 2030:
            return year
    return None


def extract_rating(text: str) -> Optional[float]:
    """Extract rating from text."""
    if not text:
        return None
    # Reject if text contains negative number pattern
    if re.search(r"-\d+\.?\d*", text):
        return None
    match = re.search(r"\b(\d+\.?\d*)\b", text)
    if match:
        try:
            rating = float(match.group(1))
            if 0 <= rating <= 10:
                return rating
        except ValueError:
            pass
    return None


def extract_votes(text: str) -> Optional[int]:
    """Extract vote count from text like '1.2M' or '1,234,567' or '2,500,000 votes'."""
    if not text:
        return None
    text = text.replace(",", "").strip()
    # Remove "votes" suffix if present
    text = text.replace("votes", "").replace("vote", "").strip()
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    for suffix, multiplier in multipliers.items():
        if text.endswith(suffix):
            try:
                return int(float(text[:-1]) * multiplier)
            except ValueError:
                pass
    try:
        return int(text)
    except ValueError:
        return None


def parse_duration(text: str) -> Optional[int]:
    """Parse duration text like '2h 30m' into minutes."""
    if not text:
        return None
    total_minutes = 0
    hours_match = re.search(r"(\d+)h", text)
    if hours_match:
        total_minutes += int(hours_match.group(1)) * 60
    minutes_match = re.search(r"(\d+)m", text)
    if minutes_match:
        total_minutes += int(minutes_match.group(1))
    return total_minutes if total_minutes > 0 else None


def delay_request() -> None:
    """Add delay between requests to be polite."""
    time.sleep(REQUEST_DELAY)


def validate_url(url: str) -> bool:
    """Basic URL validation."""
    if not url:
        return False
    url_pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(url_pattern.match(url))


def format_number(num: Optional[int]) -> str:
    """Format number with commas."""
    if num is None:
        return "N/A"
    return f"{num:,}"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def safe_get_text(element, selector: str, default: str = "") -> str:
    """Safely extract text from a BeautifulSoup element."""
    try:
        if element:
            found = element.select_one(selector)
            if found:
                return clean_text(found.get_text())
    except Exception as e:
        logger.debug(f"Error extracting {selector}: {e}")
    return default


def safe_get_attr(element, selector: str, attr: str, default: str = "") -> str:
    """Safely extract attribute from a BeautifulSoup element."""
    try:
        if element:
            found = element.select_one(selector)
            if found and found.has_attr(attr):
                return found[attr]
    except Exception as e:
        logger.debug(f"Error extracting {selector}[{attr}]: {e}")
    return default