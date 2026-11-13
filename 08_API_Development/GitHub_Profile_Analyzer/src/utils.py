"""
GitHub Profile Analyzer - Utility Functions
"""

import re
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from .config import RETRY_DELAY, CACHE_DURATION
from .logger import logger


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def format_number(num: Optional[int]) -> str:
    """Format number with K/M suffix."""
    if num is None:
        return "N/A"
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num/1_000:.1f}k"
    return str(num)


def format_date(date_str: str) -> str:
    """Format ISO date string to readable format."""
    if not date_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str


def format_datetime(date_str: str) -> str:
    """Format ISO datetime string to readable format."""
    if not date_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return date_str


def get_language_color(language: str) -> str:
    """Get color for programming language."""
    from .config import (
        COLORS, GITHUB_GREEN, GITHUB_BLUE, GITHUB_PURPLE,
        GITHUB_ORANGE, GITHUB_RED
    )
    lang_colors = {
        "python": COLORS.get("lang_python", GITHUB_BLUE),
        "javascript": COLORS.get("lang_javascript", GITHUB_ORANGE),
        "typescript": COLORS.get("lang_typescript", GITHUB_BLUE),
        "java": COLORS.get("lang_java", GITHUB_ORANGE),
        "c++": COLORS.get("lang_cpp", GITHUB_RED),
        "c#": COLORS.get("lang_cs", GITHUB_GREEN),
        "go": COLORS.get("lang_go", GITHUB_BLUE),
        "rust": COLORS.get("lang_rust", GITHUB_ORANGE),
        "php": COLORS.get("lang_php", GITHUB_PURPLE),
        "ruby": COLORS.get("lang_ruby", GITHUB_RED),
        "html": "#e34c26",
        "css": "#1572B6",
        "shell": "#89e051",
        "swift": "#FA7343",
        "kotlin": "#A97BFF",
        "scala": "#DC322F",
    }
    return lang_colors.get(language.lower(), GITHUB_BLUE)


def parse_link_header(link_header: str) -> Dict[str, str]:
    """Parse GitHub Link header for pagination."""
    links = {}
    if not link_header:
        return links
    parts = link_header.split(",")
    for part in parts:
        match = re.search(r'<([^>]+)>;\s*rel="([^"]+)"', part)
        if match:
            links[match.group(2)] = match.group(1)
    return links


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for retry with exponential backoff."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_retries} attempts failed. Last error: {e}")
            raise last_exception
        return wrapper
    return decorator


def safe_get(data: Dict, *keys, default=None) -> Any:
    """Safely get nested dictionary value."""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def calculate_repo_stats(repos: List[Dict]) -> Dict[str, Any]:
    """Calculate statistics from repository list."""
    if not repos:
        return {
            "total_repos": 0,
            "total_stars": 0,
            "total_forks": 0,
            "total_watchers": 0,
            "total_size_kb": 0,
            "languages": {},
            "top_repos": [],
            "forked_count": 0,
            "original_count": 0,
        }

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)
    total_watchers = sum(r.get("watchers_count", 0) for r in repos)
    total_size = sum(r.get("size", 0) for r in repos)

    languages = {}
    for repo in repos:
        lang = repo.get("language")
        if lang:
            languages[lang] = languages.get(lang, 0) + 1

    # Top repos by stars
    top_repos = sorted(repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:10]

    forked = sum(1 for r in repos if r.get("fork", False))
    original = len(repos) - forked

    return {
        "total_repos": len(repos),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "total_watchers": total_watchers,
        "total_size_kb": total_size,
        "languages": dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)),
        "top_repos": top_repos,
        "forked_count": forked,
        "original_count": original,
    }


def validate_github_username(username: str) -> bool:
    """Validate GitHub username format."""
    if not username:
        return False
    # GitHub usernames: alphanumeric, hyphens, max 39 chars
    pattern = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$")
    return bool(pattern.match(username))


def extract_repo_info(repo: Dict) -> Dict[str, Any]:
    """Extract relevant info from repository object."""
    return {
        "name": repo.get("name", ""),
        "full_name": repo.get("full_name", ""),
        "description": repo.get("description") or "No description",
        "language": repo.get("language"),
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "watchers": repo.get("watchers_count", 0),
        "size_kb": repo.get("size", 0),
        "created_at": repo.get("created_at"),
        "updated_at": repo.get("updated_at"),
        "pushed_at": repo.get("pushed_at"),
        "fork": repo.get("fork", False),
        "archived": repo.get("archived", False),
        "private": repo.get("private", False),
        "html_url": repo.get("html_url", ""),
        "clone_url": repo.get("clone_url", ""),
        "topics": repo.get("topics", []),
        "license": repo.get("license", {}).get("name") if repo.get("license") else None,
        "default_branch": repo.get("default_branch", "main"),
    }


def format_file_size(kb: int) -> str:
    """Format file size in KB to human readable (binary units)."""
    if kb >= 1024 * 1024:
        return f"{kb / (1024 * 1024):.1f} GB"
    if kb >= 1024:
        return f"{kb / 1024:.1f} MB"
    return f"{kb} KB"