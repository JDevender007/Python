"""
Weather API Client - Utility Functions
"""

import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from .config import RETRY_DELAY, DEFAULT_UNITS
from .logger import logger


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def kelvin_to_celsius(kelvin: float) -> float:
    """Convert Kelvin to Celsius."""
    return round(kelvin - 273.15, 1)


def kelvin_to_fahrenheit(kelvin: float) -> float:
    """Convert Kelvin to Fahrenheit."""
    return round((kelvin - 273.15) * 9/5 + 32, 1)


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return round(celsius * 9/5 + 32, 1)


def format_temperature(temp: float, units: str = DEFAULT_UNITS) -> str:
    """Format temperature with unit symbol."""
    if units == "imperial":
        return f"{temp}°F"
    return f"{temp}°C"


def format_wind_speed(speed: float, units: str = DEFAULT_UNITS) -> str:
    """Format wind speed with unit."""
    if units == "imperial":
        return f"{speed} mph"
    return f"{speed} m/s"


def format_pressure(pressure: int) -> str:
    """Format pressure in hPa."""
    return f"{pressure} hPa"


def format_humidity(humidity: int) -> str:
    """Format humidity percentage."""
    return f"{humidity}%"


def format_visibility(visibility: int) -> str:
    """Format visibility in km."""
    if visibility >= 1000:
        return f"{visibility / 1000:.1f} km"
    return f"{visibility} m"


def unix_to_datetime(timestamp: int, timezone_offset: int = 0) -> datetime:
    """Convert Unix timestamp to datetime with timezone offset."""
    utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    local_time = utc_time + timedelta(seconds=timezone_offset)
    return local_time


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime to string."""
    return dt.strftime(format_str)


def format_sun_time(timestamp: int, timezone_offset: int = 0, format_str: str = "%H:%M") -> str:
    """Format sunrise/sunset time."""
    dt = unix_to_datetime(timestamp, timezone_offset)
    return dt.strftime(format_str)


def get_weather_icon(condition_id: int, is_day: bool = True) -> str:
    """Get weather emoji/icon based on condition ID."""
    if 200 <= condition_id < 300:
        return "⛈️"  # Thunderstorm
    elif 300 <= condition_id < 400:
        return "🌦️"  # Drizzle
    elif 500 <= condition_id < 600:
        return "🌧️"  # Rain
    elif 600 <= condition_id < 700:
        return "❄️"  # Snow
    elif 700 <= condition_id < 800:
        return "🌫️"  # Atmosphere
    elif condition_id == 800:
        return "☀️" if is_day else "🌙"  # Clear
    elif 801 <= condition_id < 900:
        return "☁️"  # Clouds
    return "🌤️"


def get_temp_color(temp: float, units: str = DEFAULT_UNITS) -> str:
    """Get color based on temperature."""
    celsius = temp if units == "metric" else (temp - 32) * 5/9
    if celsius <= 0:
        return "#89b4fa"  # Cold - blue
    elif celsius <= 15:
        return "#b4befe"  # Cool - light blue
    elif celsius <= 25:
        return "#f9e2af"  # Mild - yellow
    elif celsius <= 32:
        return "#fab387"  # Warm - orange
    return "#f38ba8"  # Hot - red


def wind_deg_to_direction(degrees: int) -> str:
    """Convert wind degrees to cardinal direction."""
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    index = round(degrees / 22.5) % 16
    return directions[index]


def validate_city_name(city: str) -> bool:
    """Basic city name validation."""
    if not city or len(city.strip()) < 2:
        return False
    # Allow letters, spaces, hyphens, commas, periods
    pattern = re.compile(r"^[a-zA-Z\s\-\,\.]+$")
    return bool(pattern.match(city.strip()))


def parse_city_input(city_input: str) -> Dict[str, str]:
    """Parse city input like 'London,UK' into city and country code."""
    parts = [p.strip() for p in city_input.split(",")]
    city = parts[0]
    country = parts[1].upper() if len(parts) > 1 else ""
    return {"city": city, "country": country}


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


def safe_get(data: Dict, *keys, default=None) -> Any:
    """Safely get nested dictionary value."""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def format_number(num: Optional[float], decimals: int = 1) -> str:
    """Format number with specified decimals."""
    if num is None:
        return "N/A"
    return f"{num:.{decimals}f}"