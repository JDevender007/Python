"""
GitHub Profile Analyzer - Tracker Module
Coordinates API calls and data management.
"""

import threading
import time
from typing import List, Optional, Callable, Dict, Any
from .config import CACHE_DURATION, MAX_REPOS_PER_USER
from .api_client import GitHubAPIClient, create_client
from .models import (
    GitHubUser, Repository, UserStats, Contributor, GitHubEvent, RateLimit,
    parse_user, parse_repo, parse_contributor, parse_event, parse_rate_limit,
    calculate_user_stats
)
from .utils import calculate_repo_stats, format_file_size
from .logger import logger


class GitHubTracker:
    """Coordinates GitHub data fetching and analysis."""

    def __init__(self, token: str = None):
        self.client = create_client(token)
        self.user: Optional[GitHubUser] = None
        self.repos: List[Repository] = []
        self.stats: Optional[UserStats] = None
        self.contributors: Dict[str, List[Contributor]] = {}
        self.events: List[GitHubEvent] = []
        self.rate_limit: Optional[RateLimit] = None
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

    def fetch_user(self, username: str) -> Optional[GitHubUser]:
        """Fetch user profile."""
        if self.is_fetching:
            return None

        self.is_fetching = True
        self._update_status(f"Fetching profile for {username}...")

        try:
            cache_key = f"user_{username}"
            if self._is_cache_valid(cache_key):
                self._update_status("Using cached profile")
                return self._cache.get(cache_key)

            self._update_progress(1, 3, "Fetching user data...")
            raw_user = self.client.get_user(username)

            self._update_progress(2, 3, "Parsing user data...")
            if raw_user:
                self.user = parse_user(raw_user)
                if self.user:
                    self._cache[cache_key] = self.user
                    self._cache_timestamps[cache_key] = time.time()
                    self._update_status(f"Loaded profile: {self.user.display_name} (@{self.user.login})")
                else:
                    self._update_status("Failed to parse user data")
            else:
                self._update_status("User not found or API error")

            return self.user

        except Exception as e:
            logger.error(f"Error fetching user: {e}")
            self._update_status(f"Error: {e}")
            return None
        finally:
            self.is_fetching = False

    def fetch_repos(
        self,
        username: str,
        max_repos: int = MAX_REPOS_PER_USER,
        force_refresh: bool = False
    ) -> List[Repository]:
        """Fetch all user repositories."""
        if self.is_fetching:
            return []

        self.is_fetching = True
        self._update_status(f"Fetching repositories for {username}...")

        try:
            cache_key = f"repos_{username}"
            if not force_refresh and self._is_cache_valid(cache_key):
                self._update_status("Using cached repositories")
                return self._cache.get(cache_key, [])

            self._update_progress(1, 3, "Fetching repository list...")
            raw_repos = self.client.get_all_user_repos(username, max_repos)

            self._update_progress(2, 3, f"Processing {len(raw_repos)} repositories...")
            self.repos = []
            for raw in raw_repos:
                parsed = parse_repo(raw)
                if parsed:
                    self.repos.append(parsed)

            self._update_progress(3, 3, "Calculating statistics...")
            self.stats = calculate_user_stats(self.repos)

            self._cache[cache_key] = self.repos
            self._cache_timestamps[cache_key] = time.time()
            self._update_status(f"Loaded {len(self.repos)} repositories")

            return self.repos

        except Exception as e:
            logger.error(f"Error fetching repos: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_fetching = False

    def fetch_repo_details(self, owner: str, repo: str) -> Optional[Repository]:
        """Fetch detailed repository information."""
        if self.is_fetching:
            return None

        self.is_fetching = True
        self._update_status(f"Fetching details for {owner}/{repo}...")

        try:
            self._update_progress(1, 2, "Fetching repository data...")
            raw_repo = self.client.get_repo(owner, repo)

            self._update_progress(2, 2, "Fetching languages...")
            if raw_repo:
                parsed = parse_repo(raw_repo)
                if parsed:
                    # Fetch languages
                    lang_data = self.client.get_repo_languages(owner, repo)
                    if lang_data:
                        # Could add languages to parsed object
                        pass
                    self._update_status(f"Loaded details for {owner}/{repo}")
                    return parsed

            self._update_status("Repository not found or API error")
            return None

        except Exception as e:
            logger.error(f"Error fetching repo details: {e}")
            self._update_status(f"Error: {e}")
            return None
        finally:
            self.is_fetching = False

    def fetch_contributors(self, owner: str, repo: str) -> List[Contributor]:
        """Fetch repository contributors."""
        if self.is_fetching:
            return []

        self.is_fetching = True
        self._update_status(f"Fetching contributors for {owner}/{repo}...")

        try:
            cache_key = f"contributors_{owner}_{repo}"
            if self._is_cache_valid(cache_key):
                self._update_status("Using cached contributors")
                return self._cache.get(cache_key, [])

            self._update_progress(1, 2, "Fetching contributors...")
            raw_contributors = self.client.get_repo_contributors(owner, repo)

            self._update_progress(2, 2, "Processing contributors...")
            contributors = []
            if raw_contributors:
                for raw in raw_contributors:
                    parsed = parse_contributor(raw)
                    if parsed:
                        contributors.append(parsed)

            self.contributors[f"{owner}/{repo}"] = contributors
            self._cache[cache_key] = contributors
            self._cache_timestamps[cache_key] = time.time()
            self._update_status(f"Loaded {len(contributors)} contributors")

            return contributors

        except Exception as e:
            logger.error(f"Error fetching contributors: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_fetching = False

    def fetch_events(self, username: str, max_events: int = 50) -> List[GitHubEvent]:
        """Fetch user public events."""
        if self.is_fetching:
            return []

        self.is_fetching = True
        self._update_status(f"Fetching events for {username}...")

        try:
            cache_key = f"events_{username}"
            if self._is_cache_valid(cache_key):
                self._update_status("Using cached events")
                return self._cache.get(cache_key, [])

            self._update_progress(1, 2, "Fetching events...")
            raw_events = self.client.get_user_events(username, per_page=max_events)

            self._update_progress(2, 2, "Processing events...")
            events = []
            if raw_events:
                for raw in raw_events[:max_events]:
                    parsed = parse_event(raw)
                    if parsed:
                        events.append(parsed)

            self.events = events
            self._cache[cache_key] = events
            self._cache_timestamps[cache_key] = time.time()
            self._update_status(f"Loaded {len(events)} events")

            return events

        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_fetching = False

    def fetch_followers(self, username: str) -> List[GitHubUser]:
        """Fetch user followers."""
        if self.is_fetching:
            return []

        self.is_fetching = True
        self._update_status(f"Fetching followers for {username}...")

        try:
            self._update_progress(1, 2, "Fetching followers...")
            raw_followers = self.client.get_user_followers(username)

            self._update_progress(2, 2, "Processing followers...")
            followers = []
            if raw_followers:
                for raw in raw_followers:
                    parsed = parse_user(raw)
                    if parsed:
                        followers.append(parsed)

            self._update_status(f"Loaded {len(followers)} followers")
            return followers

        except Exception as e:
            logger.error(f"Error fetching followers: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_fetching = False

    def fetch_following(self, username: str) -> List[GitHubUser]:
        """Fetch users the user is following."""
        if self.is_fetching:
            return []

        self.is_fetching = True
        self._update_status(f"Fetching following for {username}...")

        try:
            self._update_progress(1, 2, "Fetching following...")
            raw_following = self.client.get_user_following(username)

            self._update_progress(2, 2, "Processing following...")
            following = []
            if raw_following:
                for raw in raw_following:
                    parsed = parse_user(raw)
                    if parsed:
                        following.append(parsed)

            self._update_status(f"Loaded {len(following)} following")
            return following

        except Exception as e:
            logger.error(f"Error fetching following: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_fetching = False

    def fetch_rate_limit(self) -> Optional[RateLimit]:
        """Fetch API rate limit status."""
        try:
            raw = self.client.get_rate_limit()
            if raw:
                self.rate_limit = parse_rate_limit(raw)
            return self.rate_limit
        except Exception as e:
            logger.error(f"Error fetching rate limit: {e}")
            return None

    def get_user(self) -> Optional[GitHubUser]:
        """Get cached user."""
        return self.user

    def get_repos(self) -> List[Repository]:
        """Get cached repositories."""
        return self.repos

    def get_stats(self) -> Optional[UserStats]:
        """Get cached statistics."""
        return self.stats

    def get_events(self) -> List[GitHubEvent]:
        """Get cached events."""
        return self.events

    def get_contributors(self, owner: str, repo: str) -> List[Contributor]:
        """Get cached contributors."""
        return self.contributors.get(f"{owner}/{repo}", [])

    def get_rate_limit_info(self) -> Optional[RateLimit]:
        """Get cached rate limit."""
        return self.rate_limit

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


def create_tracker(token: str = None) -> GitHubTracker:
    """Factory function to create tracker."""
    return GitHubTracker(token)