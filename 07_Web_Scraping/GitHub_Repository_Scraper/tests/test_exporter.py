"""
GitHub Repository Scraper - Unit Tests for Exporter
"""

import pytest
import csv
import json
from pathlib import Path
from src.exporter import DataExporter, create_exporter


class TestDataExporter:
    @pytest.fixture
    def exporter(self, tmp_path):
        return create_exporter(tmp_path)

    @pytest.fixture
    def sample_repos(self):
        return [
            {
                "rank": 1,
                "name": "repo1",
                "owner": "owner1",
                "full_name": "owner1 / repo1",
                "url": "/owner1/repo1",
                "description": "First repository",
                "language": "Python",
                "language_color": "#3572A5",
                "stars": 1500,
                "forks": 300,
                "today_stars": 50,
                "contributors": ["user1", "user2"],
                "topics": ["python", "cli"],
                "license": "MIT",
                "last_commit": "2024-01-15T10:00:00Z",
                "releases": "v1.0.0",
                "watchers": 10,
                "issues": 5,
                "pull_requests": 3,
                "readme_preview": "# README\nContent",
            },
            {
                "rank": 2,
                "name": "repo2",
                "owner": "owner2",
                "full_name": "owner2 / repo2",
                "url": "/owner2/repo2",
                "description": "Second repository",
                "language": "JavaScript",
                "language_color": "#f1e05a",
                "stars": 2100,
                "forks": 500,
                "today_stars": 100,
                "contributors": ["user3"],
                "topics": ["javascript", "web"],
                "license": "Apache-2.0",
                "last_commit": "2024-01-14T15:00:00Z",
                "releases": "v2.0.0",
                "watchers": 20,
                "issues": 10,
                "pull_requests": 7,
                "readme_preview": "# README\nMore content",
            },
        ]

    def test_export_csv(self, exporter, sample_repos, tmp_path):
        filepath = exporter.export_csv(sample_repos, "test.csv")

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["name"] == "repo1"
        assert rows[1]["name"] == "repo2"
        assert rows[0]["language"] == "Python"
        assert rows[0]["contributors"] == "user1; user2"
        assert rows[0]["topics"] == "python; cli"

    def test_export_json(self, exporter, sample_repos, tmp_path):
        filepath = exporter.export_json(sample_repos, "test.json")

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_repos"] == 2
        assert len(data["repos"]) == 2
        assert data["repos"][0]["name"] == "repo1"
        assert data["repos"][1]["name"] == "repo2"
        assert data["repos"][0]["language"] == "Python"
        assert data["repos"][0]["contributors"] == "user1; user2"
        assert "exported_at" in data

    def test_export_empty_list(self, exporter, tmp_path):
        csv_path = exporter.export_csv([], "empty.csv")
        json_path = exporter.export_json([], "empty.json")

        assert csv_path is None
        assert json_path is None

    def test_export_none_repos(self, exporter, tmp_path):
        csv_path = exporter.export_csv(None, "none.csv")
        json_path = exporter.export_json(None, "none.json")

        assert csv_path is None
        assert json_path is None

    def test_flatten_repo(self, exporter):
        repo = {
            "name": "Test",
            "topics": ["python", "cli"],
            "nested": {"key": "value"},
            "simple": 123,
        }

        flat = exporter._flatten_repo(repo)

        assert flat["name"] == "Test"
        assert flat["topics"] == "python; cli"
        assert flat["nested"] == '{"key": "value"}'
        assert flat["simple"] == 123