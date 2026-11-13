"""
GitHub Profile Analyzer - API Client Module
Handles HTTP requests to GitHub API.
"""

import requests
from typing import Optional, Dict, Any, List
from .config import BASE_URL, GITHUB_TOKEN, REQUEST_TIMEOUT, MAX_RETRIES
from .logger import logger
from .utils import retry_with_backoff, parse_link_header, validate_github_username


class GitHubAPIClient:
    """Client for GitHub REST API."""

    def __init__(self, token: str = None, timeout: int = REQUEST_TIMEOUT):
        self.token = token or GITHUB_TOKEN
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Profile-Analyzer/1.0",
        })
        if self.token:
            self.session.headers["Authorization"] = f"token {self.token}"

    def _make_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Make HTTP request with error handling."""
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            
            # Handle rate limiting
            if response.status_code == 403:
                remaining = response.headers.get("X-RateLimit-Remaining", "0")
                if remaining == "0":
                    reset_time = response.headers.get("X-RateLimit-Reset")
                    if reset_time:
                        import time
                        wait_time = max(int(reset_time) - int(time.time()), 0)
                        logger.warning(f"Rate limited. Reset in {wait_time}s")
            
            response.raise_for_status()
            return response.json(), response.headers
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
        return None, None

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user profile information."""
        if not validate_github_username(username):
            logger.error(f"Invalid username: {username}")
            return None

        url = f"{BASE_URL}/users/{username}"
        logger.info(f"Fetching user: {username}")
        data, headers = self._make_request(url)
        return data

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_user_repos(
        self,
        username: str,
        per_page: int = 30,
        page: int = 1,
        sort: str = "updated",
        direction: str = "desc",
        type: str = "owner"
    ) -> Optional[List[Dict]]:
        """Get user repositories with pagination."""
        if not validate_github_username(username):
            logger.error(f"Invalid username: {username}")
            return None

        url = f"{BASE_URL}/users/{username}/repos"
        params = {
            "per_page": min(per_page, 100),
            "page": page,
            "sort": sort,
            "direction": direction,
            "type": type,
        }
        logger.info(f"Fetching repos for {username} (page {page})")
        data, headers = self._make_request(url, params)
        return data

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_all_user_repos(self, username: str, max_repos: int = 1000) -> List[Dict]:
        """Get all user repositories with automatic pagination."""
        all_repos = []
        page = 1
        per_page = 100

        while len(all_repos) < max_repos:
            repos = self.get_user_repos(username, per_page=per_page, page=page)
            if not repos:
                break
            
            all_repos.extend(repos)
            
            if len(repos) < per_page:
                break
            
            page += 1

        return all_repos[:max_repos]

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_repo(self, owner: str, repo: str) -> Optional[Dict]:
        """Get repository details."""
        url = f"{BASE_URL}/repos/{owner}/{repo}"
        logger.info(f"Fetching repo: {owner}/{repo}")
        data, headers = self._make_request(url)
        return data

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_repo_languages(self, owner: str, repo: str) -> Optional[Dict]:
        """Get repository language statistics."""
        url = f"{BASE_URL}/repos/{owner}/{repo}/languages"
        logger.info(f"Fetching languages for {owner}/{repo}")
        data, headers = self._make_request(url)
        return data

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_repo_contributors(self, owner: str, repo: str, per_page: int = 30) -> Optional[List[Dict]]:
        """Get repository contributors."""
        url = f"{BASE_URL}/repos/{owner}/{repo}/contributors"
        params = {"per_page": per_page}
        logger.info(f"Fetching contributors for {owner}/{repo}")
        data, headers = self._make_request(url, params)
        return data

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_user_events(self, username: str, per_page: int = 30) -> Optional[List[Dict]]:
        """Get user public events."""
        if not validate_github_username(username):
            logger.error(f"Invalid username: {username}")
            return None

        url = f"{BASE_URL}/users/{username}/events/public"
        params = {"per_page": per_page}
        logger.info(f"Fetching events for {username}")
        data, headers = self._make_request(url, params)
        return data

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_user_followers(self, username: str, per_page: int = 30) -> Optional[List[Dict]]:
        """Get user followers."""
        if not validate_github_username(username):
            logger.error(f"Invalid username: {username}")
            return None

        url = f"{BASE_URL}/users/{username}/followers"
        params = {"per_page": per_page}
        logger.info(f"Fetching followers for {username}")
        data, headers = self._make_request(url, params)
        return data

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_user_following(self, username: str, per_page: int = 30) -> Optional[List[Dict]]:
        """Get users that the user is following."""
        if not validate_github_username(username):
            logger.error(f"Invalid username: {username}")
            return None

        url = f"{BASE_URL}/users/{username}/following"
        params = {"per_page": per_page}
        logger.info(f"Fetching following for {username}")
        data, headers = self._make_request(url, params)
        return data

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def search_repos(self, query: str, per_page: int = 30) -> Optional[Dict]:
        """Search repositories."""
        url = f"{BASE_URL}/search/repositories"
        params = {"q": query, "per_page": per_page, "sort": "stars", "order": "desc"}
        logger.info(f"Searching repos: {query}")
        data, headers = self._make_request(url, params)
        return data

    @retry_with_backoff(max_retries=MAX_RETRIES)
    def get_rate_limit(self) -> Optional[Dict]:
        """Get API rate limit status."""
        url = f"{BASE_URL}/rate_limit"
        logger.info("Fetching rate limit")
        data, headers = self._make_request(url)
        return data

    def close(self):
        """Close the session."""
        self.session.close()


def create_client(token: str = None) -> GitHubAPIClient:
    """Factory function to create API client."""
    return GitHubAPIClient(token)