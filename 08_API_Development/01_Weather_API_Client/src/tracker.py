"""
Weather API Client - Tracker Module
Coordinates API calls and data management.
"""

import threading
from typing import List, Optional, Callable, Dict, Any
from .config import DEFAULT_UNITS, DEFAULT_LANG, CACHE_DURATION
from .api_client import WeatherAPIClient, create_client
from .models import (
    CurrentWeather, ForecastData, GeocodingResult,
    parse_current_weather, parse_forecast, parse_geocoding
)
from .logger import logger


class WeatherTracker:
    """Coordinates weather data fetching and caching."""

    def __init__(self, api_key: str = None):
        self.client = create_client(api_key)
        self.current_weather: Optional[CurrentWeather] = None
        self.forecast_data: Optional[ForecastData] = None
        self.search_results: List[GeocodingResult] = []
        self.is_fetching = False
        self.progress_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
        self.units = DEFAULT_UNITS
        self.lang = DEFAULT_LANG
        self._cache = {}
        self._cache_timestamps = {}

    def set_progress_callback(self, callback: Callable[[int, int, str], None]) -> None:
        """Set callback for progress updates."""
        self.progress_callback = callback

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for status updates."""
        self.status_callback = callback

    def _update_progress(self, current: int, total: int, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(current, total, message)

    def _update_status(self, message: str) -> None:
        if self.status_callback:
            self.status_callback(message)
        logger.info(message)

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self._cache_timestamps:
            return False
        age = time.time() - self._cache_timestamps[key]
        return age < CACHE_DURATION

    def set_units(self, units: str) -> None:
        """Set temperature units (metric/imperial)."""
        self.units = units
        self._cache.clear()

    def set_language(self, lang: str) -> None:
        """Set language for weather descriptions."""
        self.lang = lang
        self._cache.clear()

    def search_cities(self, query: str, limit: int = 5) -> List[GeocodingResult]:
        """Search for cities by name."""
        self.is_fetching = True
        self._update_status(f"Searching for: {query}")

        try:
            cache_key = f"search_{query.lower()}"
            if self._is_cache_valid(cache_key):
                self._update_status("Using cached results")
                return self._cache[cache_key]

            self._update_progress(1, 2, "Fetching coordinates...")
            raw_results = self.client.get_geocoding(query, limit)

            self._update_progress(2, 2, "Processing results...")
            if raw_results:
                self.search_results = parse_geocoding(raw_results)
                self._cache[cache_key] = self.search_results
                self._cache_timestamps[cache_key] = time.time()
                self._update_status(f"Found {len(self.search_results)} cities")
            else:
                self.search_results = []
                self._update_status("No cities found")

            return self.search_results

        except Exception as e:
            logger.error(f"Error searching cities: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_fetching = False

    def fetch_current_weather(
        self,
        city: str = None,
        lat: float = None,
        lon: float = None
    ) -> Optional[CurrentWeather]:
        """Fetch current weather."""
        if self.is_fetching:
            return None

        self.is_fetching = True
        location = city or f"{lat},{lon}"
        self._update_status(f"Fetching current weather for {location}")

        try:
            cache_key = f"current_{city or f'{lat}_{lon}'}_{self.units}"
            if self._is_cache_valid(cache_key):
                self._update_status("Using cached weather data")
                return self._cache[cache_key]

            self._update_progress(1, 2, "Fetching weather data...")
            raw_data = self.client.get_current_weather(
                city=city, lat=lat, lon=lon,
                units=self.units, lang=self.lang
            )

            self._update_progress(2, 2, "Parsing weather data...")
            if raw_data:
                self.current_weather = parse_current_weather(raw_data)
                if self.current_weather:
                    self._cache[cache_key] = self.current_weather
                    self._cache_timestamps[cache_key] = time.time()
                    self._update_status(f"Weather loaded for {self.current_weather.name}")
                else:
                    self._update_status("Failed to parse weather data")
            else:
                self._update_status("Failed to fetch weather data")

            return self.current_weather

        except Exception as e:
            logger.error(f"Error fetching current weather: {e}")
            self._update_status(f"Error: {e}")
            return None
        finally:
            self.is_fetching = False

    def fetch_forecast(
        self,
        city: str = None,
        lat: float = None,
        lon: float = None,
        cnt: int = 40
    ) -> Optional[ForecastData]:
        """Fetch weather forecast."""
        if self.is_fetching:
            return None

        self.is_fetching = True
        location = city or f"{lat},{lon}"
        self._update_status(f"Fetching forecast for {location}")

        try:
            cache_key = f"forecast_{city or f'{lat}_{lon}'}_{self.units}"
            if self._is_cache_valid(cache_key):
                self._update_status("Using cached forecast")
                return self._cache[cache_key]

            self._update_progress(1, 2, "Fetching forecast data...")
            raw_data = self.client.get_forecast(
                city=city, lat=lat, lon=lon,
                units=self.units, lang=self.lang, cnt=cnt
            )

            self._update_progress(2, 2, "Parsing forecast data...")
            if raw_data:
                self.forecast_data = parse_forecast(raw_data)
                if self.forecast_data:
                    self._cache[cache_key] = self.forecast_data
                    self._cache_timestamps[cache_key] = time.time()
                    self._update_status(f"Forecast loaded ({len(self.forecast_data.list)} items)")
                else:
                    self._update_status("Failed to parse forecast data")
            else:
                self._update_status("Failed to fetch forecast data")

            return self.forecast_data

        except Exception as e:
            logger.error(f"Error fetching forecast: {e}")
            self._update_status(f"Error: {e}")
            return None
        finally:
            self.is_fetching = False

    def fetch_weather_by_coords(self, lat: float, lon: float) -> Optional[CurrentWeather]:
        """Fetch weather by coordinates."""
        return self.fetch_current_weather(lat=lat, lon=lon)

    def fetch_forecast_by_coords(self, lat: float, lon: float) -> Optional[ForecastData]:
        """Fetch forecast by coordinates."""
        return self.fetch_forecast(lat=lat, lon=lon)

    def get_current_weather(self) -> Optional[CurrentWeather]:
        """Get cached current weather."""
        return self.current_weather

    def get_forecast(self) -> Optional[ForecastData]:
        """Get cached forecast."""
        return self.forecast_data

    def get_search_results(self) -> List[GeocodingResult]:
        """Get cached search results."""
        return self.search_results

    def stop(self) -> None:
        """Stop current operation."""
        self.is_fetching = False
        self._update_status("Operation cancelled")

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        self._cache_timestamps.clear()
        self._update_status("Cache cleared")

    def close(self) -> None:
        """Close client connections."""
        self.client.close()


import time


def create_tracker(api_key: str = None) -> WeatherTracker:
    """Factory function to create tracker."""
    return WeatherTracker(api_key)