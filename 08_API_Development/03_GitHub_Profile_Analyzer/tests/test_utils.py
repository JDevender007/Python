"""
GitHub Profile Analyzer - Unit Tests for Utils
"""

import pytest
from src.utils import (
    clean_text,
    format_number,
    format_date,
    format_datetime,
    get_language_color,
    parse_link_header,
    validate_github_username,
    calculate_repo_stats,
    format_file_size,
)


class TestCleanText:
    def test_clean_text_normal(self):
        assert clean_text("  Hello   World  ") == "Hello World"

    def test_clean_text_newlines(self):
        assert clean_text("Hello\n\nWorld") == "Hello World"

    def test_clean_text_empty(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""


class TestFormatNumber:
    def test_format_number_small(self):
        assert format_number(500) == "500"
        assert format_number(999) == "999"

    def test_format_number_k(self):
        assert format_number(1500) == "1.5k"
        assert format_number(10000) == "10.0k"

    def test_format_number_m(self):
        assert format_number(1_500_000) == "1.5M"
        assert format_number(2_000_000) == "2.0M"

    def test_format_number_none(self):
        assert format_number(None) == "N/A"


class TestFormatDate:
    def test_format_date_valid(self):
        result = format_date("2024-01-15T10:30:00Z")
        assert "2024-01-15" in result

    def test_format_date_invalid(self):
        assert format_date("invalid") == "invalid"
        assert format_date("") == "N/A"
        assert format_date(None) == "N/A"


class TestFormatDatetime:
    def test_format_datetime_valid(self):
        result = format_datetime("2024-01-15T10:30:00Z")
        assert "2024-01-15" in result
        assert "10:30" in result

    def test_format_datetime_invalid(self):
        assert format_datetime("invalid") == "invalid"


class TestGetLanguageColor:
    def test_known_languages(self):
        assert get_language_color("python") == "#3572A5"
        assert get_language_color("javascript") == "#f1e05a"
        assert get_language_color("typescript") == "#3178C6"
        assert get_language_color("rust") == "#dea584"

    def test_unknown_language(self):
        assert get_language_color("unknownlang") == "#58a6ff"


class TestParseLinkHeader:
    def test_parse_link_header(self):
        header = '<https://api.github.com/user/repos?page=2>; rel="next", <https://api.github.com/user/repos?page=5>; rel="last"'
        links = parse_link_header(header)
        assert links["next"] == "https://api.github.com/user/repos?page=2"
        assert links["last"] == "https://api.github.com/user/repos?page=5"

    def test_parse_empty(self):
        assert parse_link_header("") == {}
        assert parse_link_header(None) == {}


class TestValidateGitHubUsername:
    def test_valid_usernames(self):
        assert validate_github_username("octocat") is True
        assert validate_github_username("github") is True
        assert validate_github_username("user-name") is True
        assert validate_github_username("user123") is True

    def test_invalid_usernames(self):
        assert validate_github_username("") is False
        assert validate_github_username("-user") is False
        assert validate_github_username("user-") is False
        assert validate_github_username("user@name") is False
        assert validate_github_username("a" * 40) is False


class TestCalculateRepoStats:
    def test_empty_repos(self):
        stats = calculate_repo_stats([])
        assert stats["total_repos"] == 0
        assert stats["total_stars"] == 0

    def test_with_repos(self):
        repos = [
            {"stargazers_count": 10, "forks_count": 5, "watchers_count": 3, "size": 100, "language": "Python", "fork": False},
            {"stargazers_count": 20, "forks_count": 10, "watchers_count": 5, "size": 200, "language": "JavaScript", "fork": True},
            {"stargazers_count": 5, "forks_count": 2, "watchers_count": 1, "size": 50, "language": "Python", "fork": False},
        ]
        stats = calculate_repo_stats(repos)
        assert stats["total_repos"] == 3
        assert stats["total_stars"] == 35
        assert stats["total_forks"] == 17
        assert stats["total_watchers"] == 9
        assert stats["total_size_kb"] == 350
        assert stats["languages"]["Python"] == 2
        assert stats["languages"]["JavaScript"] == 1
        assert stats["forked_count"] == 1
        assert stats["original_count"] == 2
        assert len(stats["top_repos"]) == 3
        assert stats["top_repos"][0]["stargazers_count"] == 20


class TestFormatFileSize:
    def test_kb(self):
        assert format_file_size(500) == "500 KB"
        assert format_file_size(1024) == "1.0 MB"

    def test_mb(self):
        assert format_file_size(1024 * 500) == "500.0 MB"

    def test_gb(self):
        assert format_file_size(1024 * 1024 * 2) == "2.0 GB"