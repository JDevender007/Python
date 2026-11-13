"""
News API Dashboard - Tracker Module
Coordinates API calls and data management.
"""

import threading
import time
from typing import List, Optional, Callable, Dict, Any
from .config import CACHE_DURATION, MAX_ARTICLES_CACHE, COUNTRIES, CATEGORIES
from .api_client import NewsAPIClient, create_client
from .models import Article, NewsResponse, Source, SourcesResponse, parse_news_response, parse_sources_response
from .logger import logger


class NewsTracker:
    """Coordinates news data fetching and caching."""

    def __init__(self, api_key: str = None):
        self.client = create_client(api_key)
        self.headlines: List[Article] = []
        self.all_articles: List[Article] = []
        self.sources: List[Source] = []
        self.current_filters: Dict[str, Any] = {}
        self.is_fetching = False
        self.progress_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
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

    def _get_cache_key(self, **filters) -> str:
        """Generate cache key from filters."""
        parts = []
        for k, v in sorted(filters.items()):
            if v:
                parts.append(f"{k}={v}")
        return "_".join(parts) if parts else "default"

    def fetch_top_headlines(
        self,
        country: str = "us",
        category: str = "general",
        q: str = None,
        page_size: int = 20,
        page: int = 1,
        force_refresh: bool = False
    ) -> List[Article]:
        """Fetch top headlines."""
        if self.is_fetching:
            return []

        self.is_fetching = True
        filters = {
            "country": country,
            "category": category,
            "q": q,
            "page_size": page_size,
            "page": page,
        }
        cache_key = self._get_cache_key(**filters)

        self._update_status(f"Fetching top headlines: {COUNTRIES.get(country, country)} / {category.title()}")

        try:
            if not force_refresh and self._is_cache_valid(cache_key):
                self._update_status("Using cached headlines")
                return self._cache.get(cache_key, [])

            self._update_progress(1, 3, "Requesting articles from API...")
            raw_response = self.client.get_top_headlines(
                country=country,
                category=category,
                q=q,
                page_size=page_size,
                page=page
            )

            self._update_progress(2, 3, "Processing articles...")
            if raw_response:
                response = parse_news_response(raw_response)
                if response and response.has_articles:
                    self.headlines = response.articles[:MAX_ARTICLES_CACHE]
                    self.current_filters = filters
                    self._cache[cache_key] = self.headlines
                    self._cache_timestamps[cache_key] = time.time()
                    self._update_status(f"Loaded {len(self.headlines)} articles")
                else:
                    self.headlines = []
                    self._update_status("No articles found")
            else:
                self.headlines = []
                self._update_status("Failed to fetch headlines")

            return self.headlines

        except Exception as e:
            logger.error(f"Error fetching headlines: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_fetching = False

    def fetch_everything(
        self,
        q: str = None,
        sources: str = None,
        domains: str = None,
        from_date: str = None,
        to_date: str = None,
        language: str = "en",
        sort_by: str = "publishedAt",
        page_size: int = 20,
        page: int = 1,
        force_refresh: bool = False
    ) -> List[Article]:
        """Fetch all articles matching criteria."""
        if self.is_fetching:
            return []

        self.is_fetching = True
        filters = {
            "q": q,
            "sources": sources,
            "domains": domains,
            "from_date": from_date,
            "to_date": to_date,
            "language": language,
            "sort_by": sort_by,
            "page_size": page_size,
            "page": page,
        }
        cache_key = self._get_cache_key(**filters)

        self._update_status(f"Searching articles: {q or 'all'}")

        try:
            if not force_refresh and self._is_cache_valid(cache_key):
                self._update_status("Using cached results")
                return self._cache.get(cache_key, [])

            self._update_progress(1, 3, "Searching articles...")
            raw_response = self.client.get_everything(
                q=q,
                sources=sources,
                domains=domains,
                exclude_domains=None,
                from_date=from_date,
                to_date=to_date,
                language=language,
                sort_by=sort_by,
                page_size=page_size,
                page=page
            )

            self._update_progress(2, 3, "Processing articles...")
            if raw_response:
                response = parse_news_response(raw_response)
                if response and response.has_articles:
                    self.all_articles = response.articles[:MAX_ARTICLES_CACHE]
                    self.current_filters = filters
                    self._cache[cache_key] = self.all_articles
                    self._cache_timestamps[cache_key] = time.time()
                    self._update_status(f"Found {len(self.all_articles)} articles (Total: {response.total_results})")
                else:
                    self.all_articles = []
                    self._update_status("No articles found")
            else:
                self.all_articles = []
                self._update_status("Failed to search articles")

            return self.all_articles

        except Exception as e:
            logger.error(f"Error searching articles: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_fetching = False

    def fetch_sources(
        self,
        country: str = None,
        category: str = None,
        language: str = "en",
        force_refresh: bool = False
    ) -> List[Source]:
        """Fetch available news sources."""
        if self.is_fetching:
            return []

        self.is_fetching = True
        cache_key = f"sources_{country}_{category}_{language}"

        self._update_status("Fetching news sources...")

        try:
            if not force_refresh and self._is_cache_valid(cache_key):
                self._update_status("Using cached sources")
                return self._cache.get(cache_key, [])

            self._update_progress(1, 2, "Requesting sources...")
            raw_response = self.client.get_sources(country=country, category=category, language=language)

            self._update_progress(2, 2, "Processing sources...")
            if raw_response:
                response = parse_sources_response(raw_response)
                if response:
                    self.sources = response.sources
                    self._cache[cache_key] = self.sources
                    self._cache_timestamps[cache_key] = time.time()
                    self._update_status(f"Loaded {len(self.sources)} sources")
                else:
                    self.sources = []
                    self._update_status("No sources found")
            else:
                self.sources = []
                self._update_status("Failed to fetch sources")

            return self.sources

        except Exception as e:
            logger.error(f"Error fetching sources: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_fetching = False

    def get_headlines(self) -> List[Article]:
        """Get cached headlines."""
        return self.headlines

    def get_all_articles(self) -> List[Article]:
        """Get cached search results."""
        return self.all_articles

    def get_sources_list(self) -> List[Source]:
        """Get cached sources."""
        return self.sources

    def get_current_filters(self) -> Dict[str, Any]:
        """Get current filters."""
        return self.current_filters

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


def create_tracker(api_key: str = None) -> NewsTracker:
    """Factory function to create tracker."""
    return NewsTracker(api_key)