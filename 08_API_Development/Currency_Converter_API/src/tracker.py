"""
Currency Converter API - Tracker Module
Coordinates API calls, conversions, and history management.
"""

import threading
import time
from typing import List, Optional, Callable, Dict, Any
from .config import CACHE_DURATION, POPULAR_CURRENCIES
from .api_client import CurrencyAPIClient, create_client
from .models import (
    ExchangeRatesResponse, ExchangeRate, ConversionResult,
    parse_exchange_rates, parse_pair_rate, create_conversion_result
)
from .utils import load_history, save_history, add_to_history, clear_history
from .logger import logger


class CurrencyTracker:
    """Coordinates currency conversion operations."""

    def __init__(self, api_key: str = None):
        self.client = create_client(api_key)
        self.current_rates: Optional[ExchangeRatesResponse] = None
        self.last_base = "USD"
        self.last_update = 0
        self.history: List[Dict] = []
        self.is_fetching = False
        self.progress_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
        self._rates_cache = {}
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

    def load_history(self) -> List[Dict]:
        """Load conversion history."""
        self.history = load_history()
        return self.history

    def fetch_rates(self, base: str = "USD", force: bool = False) -> Optional[ExchangeRatesResponse]:
        """Fetch latest exchange rates for base currency."""
        if self.is_fetching:
            return None

        base = base.upper()
        cache_key = f"rates_{base}"

        if not force and self._is_cache_valid(cache_key) and base == self.last_base:
            self._update_status("Using cached rates")
            return self._rates_cache.get(cache_key)

        self.is_fetching = True
        self._update_status(f"Fetching exchange rates for {base}...")

        try:
            self._update_progress(1, 2, "Requesting rates from API...")
            raw_data = self.client.get_latest_rates(base)

            self._update_progress(2, 2, "Processing rates...")
            if raw_data:
                self.current_rates = parse_exchange_rates(raw_data)
                if self.current_rates:
                    self._rates_cache[cache_key] = self.current_rates
                    self._cache_timestamps[cache_key] = time.time()
                    self.last_base = base
                    self.last_update = time.time()
                    self._update_status(f"Loaded {len(self.current_rates.rates)} rates for {base}")
                else:
                    self._update_status("Failed to parse rates")
            else:
                self._update_status("Failed to fetch rates")

            return self.current_rates

        except Exception as e:
            logger.error(f"Error fetching rates: {e}")
            self._update_status(f"Error: {e}")
            return None
        finally:
            self.is_fetching = False

    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        force_refresh: bool = False
    ) -> Optional[ConversionResult]:
        """Convert amount from one currency to another."""
        if amount <= 0:
            self._update_status("Invalid amount")
            return None

        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return create_conversion_result(
                from_currency, to_currency, amount, 1.0,
                int(time.time()), "same_currency"
            )

        self.is_fetching = True
        self._update_status(f"Converting {amount} {from_currency} to {to_currency}...")

        try:
            self._update_progress(1, 2, "Fetching exchange rate...")
            pair_data = self.client.get_pair_rate(from_currency, to_currency)

            self._update_progress(2, 2, "Calculating conversion...")
            if pair_data:
                rate = pair_data.get("rate")
                if rate:
                    result = create_conversion_result(
                        from_currency, to_currency, amount, rate,
                        pair_data.get("timestamp", int(time.time())),
                        pair_data.get("source", "unknown")
                    )
                    # Add to history
                    self.history = add_to_history(
                        from_currency, to_currency, amount, result.result, rate
                    )
                    self._update_status(f"Converted: {amount} {from_currency} = {result.result} {to_currency}")
                    return result

            self._update_status("Conversion failed")
            return None

        except Exception as e:
            logger.error(f"Error converting: {e}")
            self._update_status(f"Error: {e}")
            return None
        finally:
            self.is_fetching = False

    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get exchange rate for a pair."""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return 1.0

        if self.current_rates and from_currency == self.last_base:
            return self.current_rates.get_rate(to_currency)

        pair_data = self.client.get_pair_rate(from_currency, to_currency)
        if pair_data:
            return pair_data.get("rate")
        return None

    def get_popular_currencies(self) -> List[str]:
        """Get list of popular currencies."""
        return POPULAR_CURRENCIES.copy()

    def get_all_currencies(self) -> List[str]:
        """Get all available currencies from current rates."""
        if self.current_rates:
            return self.current_rates.get_all_currencies()
        return POPULAR_CURRENCIES.copy()

    def get_conversion_history(self) -> List[Dict]:
        """Get conversion history."""
        return self.history

    def clear_history(self) -> bool:
        """Clear conversion history."""
        success = clear_history()
        if success:
            self.history = []
            self._update_status("History cleared")
        return success

    def refresh_rates(self, base: str = None) -> Optional[ExchangeRatesResponse]:
        """Force refresh rates."""
        return self.fetch_rates(base or self.last_base, force=True)

    def stop(self) -> None:
        """Stop current operation."""
        self.is_fetching = False
        self._update_status("Operation cancelled")

    def close(self) -> None:
        """Close client connections."""
        self.client.close()


def create_tracker(api_key: str = None) -> CurrencyTracker:
    """Factory function to create tracker."""
    return CurrencyTracker(api_key)