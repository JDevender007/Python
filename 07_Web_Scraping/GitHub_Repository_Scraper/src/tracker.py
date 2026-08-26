"""
GitHub Repository Scraper - Tracker Module
Coordinates scraping, parsing, and tracking of repositories.
"""

import threading
from typing import List, Dict, Optional, Callable
from .config import DEFAULT_URL, MAX_REPOS
from .scraper import GitHubScraper, create_scraper
from .parser import RepoParser, create_parser
from .exporter import DataExporter, create_exporter
from .logger import logger


class RepoTracker:
    """Coordinates the repository scraping workflow."""

    def __init__(self):
        self.scraper = create_scraper()
        self.parser = create_parser()
        self.exporter = create_exporter()
        self.repos: List[Dict] = []
        self.detailed_repos: List[Dict] = []
        self.is_scraping = False
        self.progress_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable[[int, int, str], None]) -> None:
        """Set callback for progress updates: callback(current, total, message)."""
        self.progress_callback = callback

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for status updates: callback(message)."""
        self.status_callback = callback

    def _update_progress(self, current: int, total: int, message: str) -> None:
        """Update progress via callback."""
        if self.progress_callback:
            self.progress_callback(current, total, message)

    def _update_status(self, message: str) -> None:
        """Update status via callback."""
        if self.status_callback:
            self.status_callback(message)
        logger.info(message)

    def scrape_trending(
        self,
        url: str = DEFAULT_URL,
        language: str = "",
        since: str = "daily",
        max_repos: int = MAX_REPOS
    ) -> List[Dict]:
        """Scrape GitHub trending repositories."""
        self.is_scraping = True
        self.repos = []

        try:
            self._update_status(f"Fetching GitHub trending{' (' + language + ')' if language else ''}...")
            soup = self.scraper.fetch_trending(url, language, since)

            if not soup:
                self._update_status("Failed to fetch trending page")
                return []

            self._update_status("Parsing repository list...")
            self.repos = self.parser.parse_trending(soup)

            if max_repos and len(self.repos) > max_repos:
                self.repos = self.repos[:max_repos]

            self._update_status(f"Found {len(self.repos)} repositories")
            return self.repos

        except Exception as e:
            logger.error(f"Error scraping trending: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_scraping = False

    def scrape_user_repos(self, username: str, max_repos: int = MAX_REPOS) -> List[Dict]:
        """Scrape user repositories."""
        self.is_scraping = True
        self.repos = []

        try:
            self._update_status(f"Fetching repositories for user: {username}")
            soup = self.scraper.fetch_user_repos(username)

            if not soup:
                self._update_status(f"Failed to fetch repos for {username}")
                return []

            self._update_status("Parsing repository list...")
            self.repos = self.parser.parse_user_repos(soup)

            if max_repos and len(self.repos) > max_repos:
                self.repos = self.repos[:max_repos]

            self._update_status(f"Found {len(self.repos)} repositories")
            return self.repos

        except Exception as e:
            logger.error(f"Error scraping user repos: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_scraping = False

    def scrape_details(self, repo_indices: Optional[List[int]] = None) -> List[Dict]:
        """Scrape detailed information for selected repositories."""
        if not self.repos:
            self._update_status("No repositories loaded. Scrape first.")
            return []

        self.is_scraping = True
        self.detailed_repos = []

        target_repos = self.repos
        if repo_indices:
            target_repos = [self.repos[i] for i in repo_indices if 0 <= i < len(self.repos)]

        total = len(target_repos)

        try:
            for idx, repo in enumerate(target_repos):
                if not self.is_scraping:
                    break

                self._update_progress(idx + 1, total, f"Fetching details for: {repo['full_name']}")
                self._update_status(f"Scraping details ({idx + 1}/{total}): {repo['full_name']}")

                details = {}
                if repo.get("url"):
                    detail_soup = self.scraper.fetch_repo_details(repo["url"])
                    if detail_soup:
                        details = self.parser.parse_repo_details(detail_soup)

                detailed_repo = {**repo, **details}
                self.detailed_repos.append(detailed_repo)

            self._update_status(f"Completed scraping details for {len(self.detailed_repos)} repositories")
            return self.detailed_repos

        except Exception as e:
            logger.error(f"Error scraping details: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_scraping = False

    def stop(self) -> None:
        """Stop the scraping process."""
        self.is_scraping = False
        self._update_status("Scraping stopped by user")

    def get_repos(self) -> List[Dict]:
        """Get basic repository list."""
        return self.repos

    def get_detailed_repos(self) -> List[Dict]:
        """Get detailed repository list."""
        return self.detailed_repos if self.detailed_repos else self.repos

    def export_csv(self, filename: Optional[str] = None) -> Optional[str]:
        """Export repositories to CSV."""
        repos = self.get_detailed_repos()
        if not repos:
            self._update_status("No data to export")
            return None

        path = self.exporter.export_csv(repos, filename)
        if path:
            self._update_status(f"Exported to CSV: {path.name}")
        return str(path) if path else None

    def export_json(self, filename: Optional[str] = None) -> Optional[str]:
        """Export repositories to JSON."""
        repos = self.get_detailed_repos()
        if not repos:
            self._update_status("No data to export")
            return None

        path = self.exporter.export_json(repos, filename)
        if path:
            self._update_status(f"Exported to JSON: {path.name}")
        return str(path) if path else None

    def clear(self) -> None:
        """Clear all repository data."""
        self.repos = []
        self.detailed_repos = []
        self._update_status("Data cleared")


def create_tracker() -> RepoTracker:
    """Factory function to create a tracker instance."""
    return RepoTracker()