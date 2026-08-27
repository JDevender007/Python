"""
News API Dashboard - API Client Module
Handles HTTP requests to NewsAPI.
"""

import requests
from typing import Optional, Dict, Any, List
from .config import BASE_URL, NEWS_API_KEY, REQUEST_TIMEOUT, MAX_RETRIES
from .logger import logger
from .utils import retry_with_backoff


class NewsAPIClient:
    """Client for NewsAPI."""

    def __init__(self, api_key: str = None, timeout: int = REQUEST_TIMEOUT):
        self.api_key = api_key or NEWS_API_KEY
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "News-API-Dashboard/1.0",
        })

    def _make_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Make HTTP request with error handling."""
        try:
            # Add API key to params
            if params is None:
                params = {}
            params["apiKey"] = self.api_key

            response = self.session.get(url, params=params, timeout=self.timeout)
            
            # Handle rate limiting
            if response.status_code == 429:
                logger.warning("Rate limited by NewsAPI")
            
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
    def get_top_headlines(
        self,
        country: str = "us",
        category: str = "general",
        sources: str = None,
        q: str = None,
        page_size: int = 20,
        page: int = 1
    ) -> Optional[Dict]:
        """Get top headlines."""
        if not self.api_key:
            logger.error("API key not configured")
            return None

        url = f"{BASE_URL}/top-headlines"
        params = {
            "country": country,
            "category": category,
            "pageSize": min(page_size, 100),
            "page": page,
        }
        if sources:
            params["sources"] = sources
            # country and category cannot be used with sources
            params.pop("country", None)
            params.pop("category", None)
        if q:
            params["q"] = q

        logger.info(f"Fetching top headlines: country={country}, category={category}, q={q}")
        return self._make_request(url, params)

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_everything(
        self,
        q: str = None,
        sources: str = None,
        domains: str = None,
        exclude_domains: str = None,
        from_date: str = None,
        to_date: str = None,
        language: str = "en",
        sort_by: str = "publishedAt",
        page_size: int = 20,
        page: int = 1
    ) -> Optional[Dict]:
        """Get all articles matching criteria."""
        if not self.api_key:
            logger.error("API key not configured")
            return None

        url = f"{BASE_URL}/everything"
        params = {
            "language": language,
            "sortBy": sort_by,
            "pageSize": min(page_size, 100),
            "page": page,
        }
        if q:
            params["q"] = q
        if sources:
            params["sources"] = sources
        if domains:
            params["domains"] = domains
        if exclude_domains:
            params["excludeDomains"] = exclude_domains
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        logger.info(f"Fetching everything: q={q}, sort_by={sort_by}")
        return self._make_request(url, params)

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_sources(
        self,
        country: str = None,
        category: str = None,
        language: str = "en"
    ) -> Optional[Dict]:
        """Get available news sources."""
        if not self.api_key:
            logger.error("API key not configured")
            return None

        url = f"{BASE_URL}/sources"
        params = {"language": language}
        if country:
            params["country"] = country
        if category:
            params["category"] = category

        logger.info(f"Fetching sources: country={country}, category={category}")
        return self._make_request(url, params)

    def close(self):
        """Close the session."""
        self.session.close()


def create_client(api_key: str = None) -> NewsAPIClient:
    """Factory function to create API client."""
    return NewsAPIClient(api_key)