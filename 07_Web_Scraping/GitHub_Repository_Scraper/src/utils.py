"""
GitHub Repository Scraper - Utility Functions
"""

import re
import time
from typing import Optional, List
from .config import REQUEST_DELAY
from .logger import logger


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_number(text: str) -> Optional[int]:
    """Extract number from text like '1.2k', '1,234', '5.5M' or '50 stars today'."""
    if not text:
        return None
    text = text.replace(",", "").strip().lower()
    multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    for suffix, multiplier in multipliers.items():
        if text.endswith(suffix):
            try:
                return int(float(text[:-1]) * multiplier)
            except ValueError:
                pass
    # Try to extract first number from text
    import re
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        try:
            return int(float(match.group(1)))
        except ValueError:
            pass
    return None


def parse_relative_time(text: str) -> Optional[str]:
    """Parse relative time like '2 hours ago', '3 days ago'."""
    if not text:
        return None
    text = clean_text(text).lower()
    patterns = [
        (r"(\d+)\s*second", ("second", "seconds")),
        (r"(\d+)\s*minute", ("minute", "minutes")),
        (r"(\d+)\s*hour", ("hour", "hours")),
        (r"(\d+)\s*day", ("day", "days")),
        (r"(\d+)\s*week", ("week", "weeks")),
        (r"(\d+)\s*month", ("month", "months")),
        (r"(\d+)\s*year", ("year", "years")),
    ]
    for pattern, (singular, plural) in patterns:
        match = re.search(pattern, text)
        if match:
            num = int(match.group(1))
            unit = singular if num == 1 else plural
            return f"{match.group(1)} {unit} ago"
    return text


def validate_github_url(url: str) -> bool:
    """Validate GitHub URL."""
    if not url:
        return False
    github_pattern = re.compile(
        r"^https?://(www\.)?github\.com/"
        r"(?:[A-Za-z0-9_.-]+/)?"
        r"[A-Za-z0-9_.-]+/?",
        re.IGNORECASE,
    )
    return bool(github_pattern.match(url))


def format_number(num: Optional[int]) -> str:
    """Format number with K/M suffix."""
    if num is None:
        return "N/A"
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num/1_000:.1f}k"
    return str(num)


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def delay_request() -> None:
    """Add delay between requests to be polite."""
    time.sleep(REQUEST_DELAY)


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


def parse_language_color(style: str) -> str:
    """Extract color from style attribute like 'background-color: #ff0000'."""
    if not style:
        return ""
    match = re.search(r"background-color:\s*(#[0-9a-fA-F]{6})", style)
    return match.group(1) if match else ""