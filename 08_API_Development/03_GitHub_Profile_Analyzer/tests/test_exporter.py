"""
GitHub Profile Analyzer - Unit Tests for Exporter
"""

import pytest
import csv
import json
from pathlib import Path
from datetime import datetime
from src.exporter import GitHubExporter, create_exporter
from src.models import GitHubUser, Repository, UserStats, GitHubEvent


class TestGitHubExporter:
    @pytest.fixture
    def exporter(self, tmp_path):
        return create_exporter(tmp_path)

    @pytest.fixture
    def sample_user(self):
        return GitHubUser(
            login="octocat",
            id=1,
            avatar_url="https://github.com/images/error/octocat_happy.gif",
            name="The Octocat",
            company="GitHub",
            blog="https://github.blog",
            location="San Francisco",
            email="octocat@github.com",
            bio="There once was...",
            twitter_username="octocat",
            public_repos=8,
            public_gists=8,
            followers=9000,
            following=1,
            created_at="2011-01-25T18:44:36Z",
            updated_at="2024-01-15T10:30:00Z",
            html_url="https://github.com/octocat",
        )

    @pytest.fixture
    def sample_repos(self):
        return [
            Repository(
                id=1,
                name="Hello-World",
                full_name="octocat/Hello-World",
                owner_login="octocat",
                description="My first repo",
                language="Python",
                stars=100,
                forks=50,
                watchers=25,
                size_kb=1024,
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-15T10:30:00Z",
                pushed_at="2024-01-14T15:00:00Z",
                fork=False,
                archived=False,
                private=False,
                html_url="https://github.com/octocat/Hello-World",
                clone_url="https://github.com/octocat/Hello-World.git",
                topics=["python", "tutorial"],
                license_name="MIT",
                default_branch="main",
                open_issues=5,
            ),
            Repository(
                id=2,
                name="Test-Repo",
                full_name="octocat/Test-Repo",
                owner_login="octocat",
                description="Test repository",
                language="JavaScript",
                stars=50,
                forks=20,
                watchers=10,
                size_kb=512,
                created_at="2024-01-10T00:00:00Z",
                updated_at="2024-01-12T10:30:00Z",
                pushed_at="2024-01-11T15:00:00Z",
                fork=True,
                archived=False,
                private=False,
                html_url="https://github.com/octocat/Test-Repo",
                clone_url="https://github.com/octocat/Test-Repo.git",
                topics=["javascript", "test"],
                license_name=None,
                default_branch="main",
                open_issues=2,
            ),
        ]

    @pytest.fixture
    def sample_stats(self):
        return UserStats(
            total_repos=10,
            total_stars=500,
            total_forks=200,
            total_watchers=100,
            total_size_kb=10240,
            languages={"Python": 5, "JavaScript": 3, "Go": 2},
            top_repos=[
                Repository(id=1, name="repo1", full_name="user/repo1", owner_login="user", stars=100, forks=50, language="Python"),
                Repository(id=2, name="repo2", full_name="user/repo2", owner_login="user", stars=80, forks=30, language="JavaScript"),
            ],
            forked_count=2,
            original_count=8,
        )

    @pytest.fixture
    def sample_events(self):
        return [
            GitHubEvent(
                id="1",
                type="PushEvent",
                repo_name="octocat/Hello-World",
                repo_url="https://github.com/octocat/Hello-World",
                created_at="2024-01-15T10:30:00Z",
            ),
            GitHubEvent(
                id="2",
                type="IssuesEvent",
                repo_name="octocat/Test-Repo",
                repo_url="https://github.com/octocat/Test-Repo",
                created_at="2024-01-14T15:00:00Z",
            ),
        ]

    def test_export_user_profile_csv(self, exporter, sample_user):
        filepath = exporter.export_user_profile(sample_user)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0] == ["Field", "Value"]
        assert ["Username", "octocat"] in rows
        assert ["Name", "The Octocat"] in rows
        assert ["Followers", "9000"] in rows

    def test_export_repositories_csv(self, exporter, sample_repos):
        filepath = exporter.export_repositories(sample_repos)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0][0] == "Name"
        assert len(rows) == 3  # header + 2 repos

    def test_export_statistics_csv(self, exporter, sample_stats):
        filepath = exporter.export_statistics(sample_stats)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0] == ["Metric", "Value"]
        assert ["Total Repositories", "10"] in rows
        assert ["Total Stars", "500"] in rows
        assert ["Top Language", "Python"] in rows

    def test_export_events_csv(self, exporter, sample_events):
        filepath = exporter.export_events(sample_events)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0] == ["Type", "Repository", "Created At", "URL"]
        assert len(rows) == 3  # header + 2 events

    def test_export_user_profile_json(self, exporter, sample_user):
        filepath = exporter.export_user_profile_json(sample_user)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["profile"]["login"] == "octocat"
        assert data["profile"]["name"] == "The Octocat"
        assert data["profile"]["followers"] == 9000
        assert "exported_at" in data

    def test_export_repositories_json(self, exporter, sample_repos):
        filepath = exporter.export_repositories_json(sample_repos)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_repos"] == 2
        assert len(data["repositories"]) == 2
        assert data["repositories"][0]["name"] == "Hello-World"
        assert data["repositories"][0]["language"] == "Python"

    def test_export_statistics_json(self, exporter, sample_stats):
        filepath = exporter.export_statistics_json(sample_stats)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["statistics"]["total_repos"] == 10
        assert data["statistics"]["total_stars"] == 500
        assert data["statistics"]["top_language"] == "Python"
        assert len(data["statistics"]["top_repos"]) == 2

    def test_export_events_json(self, exporter, sample_events):
        filepath = exporter.export_events_json(sample_events)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_events"] == 2
        assert len(data["events"]) == 2
        assert data["events"][0]["type"] == "PushEvent"

    def test_export_empty_user(self, exporter):
        csv_path = exporter.export_user_profile(None)
        json_path = exporter.export_user_profile_json(None)
        assert csv_path is None
        assert json_path is None

    def test_export_empty_repos(self, exporter):
        csv_path = exporter.export_repositories([])
        json_path = exporter.export_repositories_json([])
        assert csv_path is None
        assert json_path is None

    def test_export_empty_stats(self, exporter):
        csv_path = exporter.export_statistics(None)
        json_path = exporter.export_statistics_json(None)
        assert csv_path is None
        assert json_path is None

    def test_export_empty_events(self, exporter):
        csv_path = exporter.export_events([])
        json_path = exporter.export_events_json([])
        assert csv_path is None
        assert json_path is None