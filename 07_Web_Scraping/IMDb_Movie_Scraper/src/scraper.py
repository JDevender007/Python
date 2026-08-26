"""
IMDb Movie Scraper - Scraper Module
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional
from .config import DEFAULT_URL, HEADERS, REQUEST_TIMEOUT, MAX_MOVIES
from .logger import logger
from .utils import delay_request, validate_url


class IMDbScraper:
    """Handles HTTP requests and HTML fetching for IMDb."""

    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a webpage and return HTML content."""
        if not validate_url(url):
            logger.error(f"Invalid URL: {url}")
            return None

        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            logger.info(f"Successfully fetched: {url} (Status: {response.status_code})")
            return response.text
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout for: {url}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
        return None

    def fetch_top_movies(self, url: str = DEFAULT_URL) -> Optional[BeautifulSoup]:
        """Fetch and parse the IMDb Top 250 page."""
        html = self.fetch_page(url)
        if html:
            return BeautifulSoup(html, "html.parser")
        return None

    def fetch_movie_details(self, movie_url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse individual movie detail page."""
        if not movie_url.startswith("http"):
            movie_url = f"https://www.imdb.com{movie_url}"
        delay_request()
        html = self.fetch_page(movie_url)
        if html:
            return BeautifulSoup(html, "html.parser")
        return None

    def close(self) -> None:
        """Close the session."""
        self.session.close()
        logger.debug("Session closed")


def create_scraper() -> IMDbScraper:
    """Factory function to create a scraper instance."""
    return IMDbScraper()