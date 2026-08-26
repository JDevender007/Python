"""
GitHub Profile Analyzer - Unit Tests for Models
"""

import pytest
from src.models import (
    GitHubUser, Repository, UserStats, Contributor, GitHubEvent, RateLimit,
    parse_user, parse_repo, parse_contributor, parse_event, parse_rate_limit,
    calculate_user_stats
)


class TestDataClasses:
    def test_github_user(self):
        user = GitHubUser(
            login="octocat",
            id=1,
            avatar_url="https://github.com/images/error/octocat_happy.gif",
            name="The Octocat",
            company="GitHub",
            blog="https://github.blog",
            location="San Francisco",
            email="octocat@github.com",
            bio="There once was...",
            public_repos=8,
            public_gists=8,
            followers=9000,
            following=1,
            created_at="2011-01-25T18:44:36Z",
            updated_at="2024-01-15T10:30:00Z",
            html_url="https://github.com/octocat",
        )
        assert user.login == "octocat"
        assert user.display_name == "The Octocat"
        assert user.profile_url == "https://github.com/octocat"

    def test_github_user_no_name(self):
        user = GitHubUser(login="testuser", id=2, avatar_url="", name=None)
        assert user.display_name == "testuser"

    def test_repository(self):
        repo = Repository(
            id=123,
            name="Hello-World",
            full_name="octocat/Hello-World",
            owner_login="octocat",
            description="My first repo",
            language="Python",
            stars=100,
            forks=50,
            watchers=25,
            size_kb=1024,
            html_url="https://github.com/octocat/Hello-World",
        )
        assert repo.full_name == "octocat/Hello-World"
        assert repo.url == "https://github.com/octocat/Hello-World"

    def test_user_stats(self):
        stats = UserStats(
            total_repos=10,
            total_stars=500,
            total_forks=200,
            total_watchers=100,
            languages={"Python": 5, "JavaScript": 3, "Go": 2},
        )
        assert stats.top_language == "Python"
        assert stats.language_diversity == 3

    def test_contributor(self):
        contrib = Contributor(
            login="contributor1",
            id=456,
            avatar_url="https://github.com/images/error/contributor_happy.gif",
            contributions=50,
            html_url="https://github.com/contributor1",
        )
        assert contrib.profile_url == "https://github.com/contributor1"

    def test_github_event(self):
        event = GitHubEvent(
            id="12345",
            type="PushEvent",
            repo_name="octocat/Hello-World",
            repo_url="https://github.com/octocat/Hello-World",
            created_at="2024-01-15T10:30:00Z",
        )
        assert event.display_type == "📤 Pushed to"

    def test_rate_limit(self):
        rate = RateLimit(limit=5000, remaining=4999, reset_timestamp=1705315200, used=1)
        assert rate.percentage_used == 0.02


class TestParsers:
    def test_parse_user(self):
        data = {
            "login": "octocat",
            "id": 1,
            "avatar_url": "https://github.com/images/error/octocat_happy.gif",
            "name": "The Octocat",
            "company": "GitHub",
            "blog": "https://github.blog",
            "location": "San Francisco",
            "email": "octocat@github.com",
            "bio": "There once was...",
            "twitter_username": "octocat",
            "public_repos": 8,
            "public_gists": 8,
            "followers": 9000,
            "following": 1,
            "created_at": "2011-01-25T18:44:36Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "html_url": "https://github.com/octocat",
            "type": "User",
            "site_admin": False,
        }
        user = parse_user(data)
        assert user is not None
        assert user.login == "octocat"
        assert user.name == "The Octocat"
        assert user.followers == 9000

    def test_parse_user_minimal(self):
        data = {"login": "test", "id": 1, "avatar_url": "", "html_url": "https://github.com/test"}
        user = parse_user(data)
        assert user is not None
        assert user.login == "test"

    def test_parse_repo(self):
        data = {
            "id": 123,
            "name": "Hello-World",
            "full_name": "octocat/Hello-World",
            "owner": {"login": "octocat"},
            "description": "My first repo",
            "language": "Python",
            "stargazers_count": 100,
            "forks_count": 50,
            "watchers_count": 25,
            "size": 1024,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "pushed_at": "2024-01-14T15:00:00Z",
            "fork": False,
            "archived": False,
            "private": False,
            "html_url": "https://github.com/octocat/Hello-World",
            "clone_url": "https://github.com/octocat/Hello-World.git",
            "topics": ["python", "tutorial"],
            "license": {"name": "MIT"},
            "default_branch": "main",
            "open_issues_count": 5,
        }
        repo = parse_repo(data)
        assert repo is not None
        assert repo.name == "Hello-World"
        assert repo.stars == 100
        assert repo.language == "Python"
        assert repo.topics == ["python", "tutorial"]
        assert repo.license_name == "MIT"

    def test_parse_repo_minimal(self):
        data = {"id": 1, "name": "test", "full_name": "user/test", "owner": {"login": "user"}}
        repo = parse_repo(data)
        assert repo is not None
        assert repo.name == "test"

    def test_parse_contributor(self):
        data = {
            "login": "contributor1",
            "id": 456,
            "avatar_url": "https://github.com/images/error/contributor_happy.gif",
            "contributions": 50,
            "html_url": "https://github.com/contributor1",
        }
        contrib = parse_contributor(data)
        assert contrib is not None
        assert contrib.login == "contributor1"
        assert contrib.contributions == 50

    def test_parse_event(self):
        data = {
            "id": "12345",
            "type": "PushEvent",
            "repo": {"name": "octocat/Hello-World", "url": "https://github.com/octocat/Hello-World"},
            "created_at": "2024-01-15T10:30:00Z",
            "payload": {"commits": [{"message": "Initial commit"}]},
        }
        event = parse_event(data)
        assert event is not None
        assert event.type == "PushEvent"
        assert event.display_type == "📤 Pushed to"

    def test_parse_event_types(self):
        types = {
            "CreateEvent": "📝 Created",
            "IssuesEvent": "🐛 Issue",
            "PullRequestEvent": "🔀 Pull Request",
            "WatchEvent": "⭐ Starred",
            "ForkEvent": "🍴 Forked",
            "ReleaseEvent": "📦 Released",
            "DeleteEvent": "🗑️ Deleted",
        }
        for event_type, expected in types.items():
            data = {"type": event_type, "repo": {"name": "test/repo"}}
            event = parse_event(data)
            assert event.display_type == expected

    def test_parse_rate_limit(self):
        data = {
            "resources": {
                "core": {
                    "limit": 5000,
                    "remaining": 4999,
                    "reset": 1705315200,
                    "used": 1,
                }
            }
        }
        rate = parse_rate_limit(data)
        assert rate is not None
        assert rate.limit == 5000
        assert rate.remaining == 4999


class TestCalculateUserStats:
    def test_empty_repos(self):
        stats = calculate_user_stats([])
        assert stats.total_repos == 0

    def test_with_repos(self):
        from src.models import Repository
        repos = [
            Repository(id=1, name="repo1", full_name="user/repo1", owner_login="user", stars=10, forks=5, language="Python"),
            Repository(id=2, name="repo2", full_name="user/repo2", owner_login="user", stars=20, forks=10, language="JavaScript"),
            Repository(id=3, name="repo3", full_name="user/repo3", owner_login="user", stars=5, forks=2, language="Python"),
        ]
        stats = calculate_user_stats(repos)
        assert stats.total_repos == 3
        assert stats.total_stars == 35
        assert stats.total_forks == 17
        assert stats.languages["Python"] == 2
        assert stats.languages["JavaScript"] == 1
        assert stats.top_language == "Python"
        assert len(stats.top_repos) == 3
        assert stats.top_repos[0].stars == 20