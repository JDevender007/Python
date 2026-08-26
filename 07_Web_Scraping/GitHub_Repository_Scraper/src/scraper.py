"""
GitHub Repository Scraper - Scraper Module
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional
from .config import DEFAULT_URL, HEADERS, REQUEST_TIMEOUT, MAX_REPOS
from .logger import logger
from .utils import delay_request, validate_github_url


class GitHubScraper:
    """Handles HTTP requests and HTML fetching for GitHub."""

    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a webpage and return HTML content."""
        if not validate_github_url(url) and "github.com" not in url:
            logger.error(f"Invalid GitHub URL: {url}")
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

    def fetch_trending(self, url: str = DEFAULT_URL, language: str = "", since: str = "daily") -> Optional[BeautifulSoup]:
        """Fetch and parse GitHub trending page."""
        if language:
            url = f"{url}/{language}?since={since}"
        elif since != "daily":
            url = f"{url}?since={since}"
        html = self.fetch_page(url)
        if html:
            return BeautifulSoup(html, "html.parser")
        return None

    def fetch_user_repos(self, username: str) -> Optional[BeautifulSoup]:
        """Fetch user repositories page."""
        url = f"https://github.com/{username}?tab=repositories"
        html = self.fetch_page(url)
        if html:
            return BeautifulSoup(html, "html.parser")
        return None

    def fetch_repo_details(self, repo_url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse individual repository page."""
        if not repo_url.startswith("http"):
            repo_url = f"https://github.com{repo_url}"
        delay_request()
        html = self.fetch_page(repo_url)
        if html:
            return BeautifulSoup(html, "html.parser")
        return None

    def close(self) -> None:
        """Close the session."""
        self.session.close()
        logger.debug("Session closed")


def create_scraper() -> GitHubScraper:
    """Factory function to create a scraper instance."""
    return GitHubScraper()