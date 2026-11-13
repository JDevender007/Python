"""
Weather API Client - API Client Module
Handles HTTP requests to OpenWeatherMap API.
"""

import requests
from typing import Optional, Dict, Any, List
from .config import BASE_URL, GEO_URL, API_KEY, REQUEST_TIMEOUT, MAX_RETRIES
from .logger import logger
from .utils import retry_with_backoff


class WeatherAPIClient:
    """Client for OpenWeatherMap API."""

    def __init__(self, api_key: str = None, timeout: int = REQUEST_TIMEOUT):
        self.api_key = api_key or API_KEY
        self.timeout = timeout
        self.session = requests.Session()
        self.session.params = {"appid": self.api_key}

    def _make_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Make HTTP request with error handling."""
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {url}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
        except ValueError as e:
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        return None

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_current_weather(
        self,
        city: str = None,
        lat: float = None,
        lon: float = None,
        units: str = "metric",
        lang: str = "en"
    ) -> Optional[Dict]:
        """Get current weather data."""
        if not self.api_key:
            logger.error("API key not configured")
            return None

        params = {"units": units, "lang": lang}

        if lat is not None and lon is not None:
            params["lat"] = lat
            params["lon"] = lon
        elif city:
            params["q"] = city
        else:
            logger.error("Either city or coordinates required")
            return None

        url = f"{BASE_URL}/weather"
        logger.info(f"Fetching current weather for: {city or f'{lat},{lon}'}")
        return self._make_request(url, params)

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_forecast(
        self,
        city: str = None,
        lat: float = None,
        lon: float = None,
        units: str = "metric",
        lang: str = "en",
        cnt: int = 40
    ) -> Optional[Dict]:
        """Get 5-day forecast (3-hour intervals)."""
        if not self.api_key:
            logger.error("API key not configured")
            return None

        params = {"units": units, "lang": lang, "cnt": cnt}

        if lat is not None and lon is not None:
            params["lat"] = lat
            params["lon"] = lon
        elif city:
            params["q"] = city
        else:
            logger.error("Either city or coordinates required")
            return None

        url = f"{BASE_URL}/forecast"
        logger.info(f"Fetching forecast for: {city or f'{lat},{lon}'}")
        return self._make_request(url, params)

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_geocoding(
        self,
        city: str,
        limit: int = 5
    ) -> Optional[List[Dict]]:
        """Get coordinates for city name."""
        if not self.api_key:
            logger.error("API key not configured")
            return None

        params = {"q": city, "limit": limit}
        url = f"{GEO_URL}/direct"
        logger.info(f"Geocoding: {city}")
        return self._make_request(url, params)

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_reverse_geocoding(
        self,
        lat: float,
        lon: float,
        limit: int = 5
    ) -> Optional[List[Dict]]:
        """Get city name for coordinates."""
        if not self.api_key:
            logger.error("API key not configured")
            return None

        params = {"lat": lat, "lon": lon, "limit": limit}
        url = f"{GEO_URL}/reverse"
        logger.info(f"Reverse geocoding: {lat},{lon}")
        return self._make_request(url, params)

    def get_weather_by_zip(self, zip_code: str, country: str = "US", units: str = "metric") -> Optional[Dict]:
        """Get weather by ZIP code."""
        if not self.api_key:
            logger.error("API key not configured")
            return None

        params = {"zip": f"{zip_code},{country}", "units": units}
        url = f"{BASE_URL}/weather"
        logger.info(f"Fetching weather for ZIP: {zip_code}")
        return self._make_request(url, params)

    def close(self):
        """Close the session."""
        self.session.close()


def create_client(api_key: str = None) -> WeatherAPIClient:
    """Factory function to create API client."""
    return WeatherAPIClient(api_key)