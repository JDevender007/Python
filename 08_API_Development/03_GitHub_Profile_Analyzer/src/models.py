"""
GitHub Profile Analyzer - Data Models
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class GitHubUser:
    """GitHub user profile."""
    login: str
    id: int
    avatar_url: str
    name: Optional[str] = None
    company: Optional[str] = None
    blog: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None
    twitter_username: Optional[str] = None
    public_repos: int = 0
    public_gists: int = 0
    followers: int = 0
    following: int = 0
    created_at: str = ""
    updated_at: str = ""
    html_url: str = ""
    type: str = "User"
    site_admin: bool = False

    @property
    def display_name(self) -> str:
        return self.name or self.login

    @property
    def profile_url(self) -> str:
        return f"https://github.com/{self.login}"

    @property
    def account_age_days(self) -> int:
        try:
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            return (datetime.now() - created.replace(tzinfo=None)).days
        except Exception:
            return 0


@dataclass
class Repository:
    """GitHub repository."""
    id: int
    name: str
    full_name: str
    owner_login: str
    description: Optional[str] = None
    language: Optional[str] = None
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    size_kb: int = 0
    created_at: str = ""
    updated_at: str = ""
    pushed_at: str = ""
    fork: bool = False
    archived: bool = False
    private: bool = False
    html_url: str = ""
    clone_url: str = ""
    topics: List[str] = field(default_factory=list)
    license_name: Optional[str] = None
    default_branch: str = "main"
    open_issues: int = 0

    @property
    def url(self) -> str:
        return f"https://github.com/{self.full_name}"

    @property
    def language_color(self) -> str:
        from .utils import get_language_color
        return get_language_color(self.language) if self.language else "#58a6ff"


@dataclass
class LanguageStats:
    """Language statistics for a repository."""
    language: str
    bytes: int

    @property
    def percentage(self) -> float:
        # Will be calculated externally
        return 0.0


@dataclass
class UserStats:
    """Aggregated user statistics."""
    total_repos: int = 0
    total_stars: int = 0
    total_forks: int = 0
    total_watchers: int = 0
    total_size_kb: int = 0
    languages: Dict[str, int] = field(default_factory=dict)
    top_repos: List[Repository] = field(default_factory=list)
    forked_count: int = 0
    original_count: int = 0

    @property
    def top_language(self) -> Optional[str]:
        if not self.languages:
            return None
        return max(self.languages.items(), key=lambda x: x[1])[0]

    @property
    def language_diversity(self) -> int:
        return len(self.languages)


@dataclass
class Contributor:
    """Repository contributor."""
    login: str
    id: int
    avatar_url: str
    contributions: int
    html_url: str = ""

    @property
    def profile_url(self) -> str:
        return f"https://github.com/{self.login}"


@dataclass
class GitHubEvent:
    """GitHub public event."""
    id: str
    type: str
    repo_name: str
    repo_url: str
    created_at: str
    payload: Dict = field(default_factory=dict)

    @property
    def display_type(self) -> str:
        types = {
            "PushEvent": "📤 Pushed to",
            "CreateEvent": "📝 Created",
            "IssuesEvent": "🐛 Issue",
            "PullRequestEvent": "🔀 Pull Request",
            "WatchEvent": "⭐ Starred",
            "ForkEvent": "🍴 Forked",
            "ReleaseEvent": "📦 Released",
            "DeleteEvent": "🗑️ Deleted",
        }
        return types.get(self.type, self.type)


@dataclass
class RateLimit:
    """API rate limit info."""
    limit: int
    remaining: int
    reset_timestamp: int
    used: int = 0

    @property
    def reset_time(self) -> datetime:
        return datetime.fromtimestamp(self.reset_timestamp)

    @property
    def reset_in_seconds(self) -> int:
        return max(self.reset_timestamp - int(datetime.now().timestamp()), 0)

    @property
    def percentage_used(self) -> float:
        if self.limit == 0:
            return 0.0
        return (self.used / self.limit) * 100


def parse_user(data: Dict) -> Optional[GitHubUser]:
    """Parse user from API response."""
    try:
        return GitHubUser(
            login=data.get("login", ""),
            id=data.get("id", 0),
            avatar_url=data.get("avatar_url", ""),
            name=data.get("name"),
            company=data.get("company"),
            blog=data.get("blog"),
            location=data.get("location"),
            email=data.get("email"),
            bio=data.get("bio"),
            twitter_username=data.get("twitter_username"),
            public_repos=data.get("public_repos", 0),
            public_gists=data.get("public_gists", 0),
            followers=data.get("followers", 0),
            following=data.get("following", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            html_url=data.get("html_url", ""),
            type=data.get("type", "User"),
            site_admin=data.get("site_admin", False),
        )
    except Exception as e:
        return None


def parse_repo(data: Dict) -> Optional[Repository]:
    """Parse repository from API response."""
    try:
        owner = data.get("owner", {})
        license_info = data.get("license")
        return Repository(
            id=data.get("id", 0),
            name=data.get("name", ""),
            full_name=data.get("full_name", ""),
            owner_login=owner.get("login", ""),
            description=data.get("description"),
            language=data.get("language"),
            stars=data.get("stargazers_count", 0),
            forks=data.get("forks_count", 0),
            watchers=data.get("watchers_count", 0),
            size_kb=data.get("size", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            pushed_at=data.get("pushed_at", ""),
            fork=data.get("fork", False),
            archived=data.get("archived", False),
            private=data.get("private", False),
            html_url=data.get("html_url", ""),
            clone_url=data.get("clone_url", ""),
            topics=data.get("topics", []),
            license_name=license_info.get("name") if license_info else None,
            default_branch=data.get("default_branch", "main"),
            open_issues=data.get("open_issues_count", 0),
        )
    except Exception as e:
        return None


def parse_contributor(data: Dict) -> Optional[Contributor]:
    """Parse contributor from API response."""
    try:
        return Contributor(
            login=data.get("login", ""),
            id=data.get("id", 0),
            avatar_url=data.get("avatar_url", ""),
            contributions=data.get("contributions", 0),
            html_url=data.get("html_url", ""),
        )
    except Exception:
        return None


def parse_event(data: Dict) -> Optional[GitHubEvent]:
    """Parse event from API response."""
    try:
        repo = data.get("repo", {})
        return GitHubEvent(
            id=data.get("id", ""),
            type=data.get("type", ""),
            repo_name=repo.get("name", ""),
            repo_url=repo.get("url", ""),
            created_at=data.get("created_at", ""),
            payload=data.get("payload", {}),
        )
    except Exception:
        return None


def parse_rate_limit(data: Dict) -> Optional[RateLimit]:
    """Parse rate limit from API response."""
    try:
        core = data.get("resources", {}).get("core", {})
        return RateLimit(
            limit=core.get("limit", 5000),
            remaining=core.get("remaining", 0),
            reset_timestamp=core.get("reset", 0),
            used=core.get("used", 0),
        )
    except Exception:
        return None


def calculate_user_stats(repos: List[Repository]) -> UserStats:
    """Calculate aggregated statistics from repositories."""
    if not repos:
        return UserStats()

    total_stars = sum(r.stars for r in repos)
    total_forks = sum(r.forks for r in repos)
    total_watchers = sum(r.watchers for r in repos)
    total_size = sum(r.size_kb for r in repos)

    languages = {}
    for repo in repos:
        if repo.language:
            languages[repo.language] = languages.get(repo.language, 0) + 1

    top_repos = sorted(repos, key=lambda x: x.stars, reverse=True)[:10]

    forked = sum(1 for r in repos if r.fork)
    original = len(repos) - forked

    return UserStats(
        total_repos=len(repos),
        total_stars=total_stars,
        total_forks=total_forks,
        total_watchers=total_watchers,
        total_size_kb=total_size,
        languages=dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)),
        top_repos=top_repos,
        forked_count=forked,
        original_count=original,
    )