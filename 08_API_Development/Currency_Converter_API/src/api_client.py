"""
Currency Converter API - API Client Module
Handles HTTP requests to exchange rate APIs.
"""

import requests
from typing import Optional, Dict, Any, List
from .config import BASE_URL, FALLBACK_URL, API_KEY, REQUEST_TIMEOUT, MAX_RETRIES
from .logger import logger
from .utils import retry_with_backoff, validate_currency_code


class CurrencyAPIClient:
    """Client for exchange rate APIs."""

    def __init__(self, api_key: str = None, timeout: int = REQUEST_TIMEOUT):
        self.api_key = api_key or API_KEY
        self.timeout = timeout
        self.session = requests.Session()
        self.use_fallback = False

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
    def get_latest_rates(self, base: str = "USD") -> Optional[Dict]:
        """Get latest exchange rates for a base currency."""
        if not validate_currency_code(base):
            logger.error(f"Invalid base currency: {base}")
            return None

        if self.api_key and not self.use_fallback:
            url = f"{BASE_URL}/{self.api_key}/latest/{base.upper()}"
            logger.info(f"Fetching rates from primary API for base: {base}")
            data = self._make_request(url)
            if data and data.get("result") == "success":
                return self._normalize_response(data, base)
            logger.warning("Primary API failed, trying fallback...")
            self.use_fallback = True

        # Fallback API
        url = f"{FALLBACK_URL}/{base.upper()}"
        logger.info(f"Fetching rates from fallback API for base: {base}")
        data = self._make_request(url)
        if data:
            return self._normalize_fallback(data, base)
        return None

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_pair_rate(self, from_currency: str, to_currency: str) -> Optional[Dict]:
        """Get exchange rate for a specific currency pair."""
        if not validate_currency_code(from_currency) or not validate_currency_code(to_currency):
            logger.error(f"Invalid currency codes: {from_currency}, {to_currency}")
            return None

        if self.api_key and not self.use_fallback:
            url = f"{BASE_URL}/{self.api_key}/pair/{from_currency.upper()}/{to_currency.upper()}"
            logger.info(f"Fetching pair rate from primary API: {from_currency}/{to_currency}")
            data = self._make_request(url)
            if data and data.get("result") == "success":
                return {
                    "base": from_currency.upper(),
                    "target": to_currency.upper(),
                    "rate": data.get("conversion_rate"),
                    "timestamp": data.get("time_last_update_unix"),
                    "source": "primary"
                }
            logger.warning("Primary API failed, trying fallback...")
            self.use_fallback = True

        # Fallback: get all rates for base and extract target
        rates_data = self.get_latest_rates(from_currency)
        if rates_data and to_currency.upper() in rates_data.get("rates", {}):
            return {
                "base": from_currency.upper(),
                "target": to_currency.upper(),
                "rate": rates_data["rates"][to_currency.upper()],
                "timestamp": rates_data.get("timestamp"),
                "source": "fallback"
            }
        return None

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_historical_rates(self, base: str, date: str) -> Optional[Dict]:
        """Get historical exchange rates for a specific date (YYYY-MM-DD)."""
        if not validate_currency_code(base):
            logger.error(f"Invalid base currency: {base}")
            return None

        if self.api_key and not self.use_fallback:
            url = f"{BASE_URL}/{self.api_key}/history/{base.upper()}/{date}"
            logger.info(f"Fetching historical rates from primary API for {date}")
            data = self._make_request(url)
            if data and data.get("result") == "success":
                return self._normalize_response(data, base)
        return None

    def _normalize_response(self, data: Dict, base: str) -> Dict:
        """Normalize primary API response."""
        return {
            "base": base.upper(),
            "rates": data.get("conversion_rates", {}),
            "timestamp": data.get("time_last_update_unix"),
            "date": data.get("time_last_update_utc"),
            "source": "primary"
        }

    def _normalize_fallback(self, data: Dict, base: str) -> Dict:
        """Normalize fallback API response."""
        return {
            "base": base.upper(),
            "rates": data.get("rates", {}),
            "timestamp": data.get("time_last_update_unix", 0),
            "date": data.get("date", ""),
            "source": "fallback"
        }

    def get_supported_currencies(self) -> Optional[Dict[str, str]]:
        """Get list of supported currencies with names."""
        if self.api_key and not self.use_fallback:
            url = f"{BASE_URL}/{self.api_key}/codes"
            data = self._make_request(url)
            if data and data.get("result") == "success":
                return {code: name for code, name in data.get("supported_codes", [])}
        return None

    def close(self):
        """Close the session."""
        self.session.close()


def create_client(api_key: str = None) -> CurrencyAPIClient:
    """Factory function to create API client."""
    return CurrencyAPIClient(api_key)