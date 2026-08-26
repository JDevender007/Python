"""
GitHub Repository Scraper - Unit Tests for Utils
"""

import pytest
from src.utils import (
    clean_text,
    extract_number,
    parse_relative_time,
    format_number,
    truncate_text,
    validate_github_url,
    parse_language_color,
)


class TestCleanText:
    def test_clean_text_normal(self):
        assert clean_text("  Hello   World  ") == "Hello World"

    def test_clean_text_newlines(self):
        assert clean_text("Hello\n\nWorld") == "Hello World"

    def test_clean_text_empty(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""

    def test_clean_text_tabs(self):
        assert clean_text("Hello\t\tWorld") == "Hello World"


class TestExtractNumber:
    def test_extract_number_plain(self):
        assert extract_number("1000") == 1000
        assert extract_number("1,000") == 1000

    def test_extract_number_with_suffix(self):
        assert extract_number("1.5k") == 1500
        assert extract_number("2.5M") == 2_500_000
        assert extract_number("1B") == 1_000_000_000

    def test_extract_number_uppercase(self):
        assert extract_number("1.5K") == 1500
        assert extract_number("2.5M") == 2_500_000

    def test_extract_number_invalid(self):
        assert extract_number("abc") is None
        assert extract_number("") is None
        assert extract_number(None) is None


class TestParseRelativeTime:
    def test_parse_seconds(self):
        assert parse_relative_time("5 seconds ago") == "5 seconds ago"
        assert parse_relative_time("30 seconds ago") == "30 seconds ago"

    def test_parse_minutes(self):
        assert parse_relative_time("5 minutes ago") == "5 minutes ago"

    def test_parse_hours(self):
        assert parse_relative_time("2 hours ago") == "2 hours ago"

    def test_parse_days(self):
        assert parse_relative_time("3 days ago") == "3 days ago"

    def test_parse_weeks(self):
        assert parse_relative_time("1 week ago") == "1 week ago"

    def test_parse_months(self):
        assert parse_relative_time("2 months ago") == "2 months ago"

    def test_parse_years(self):
        assert parse_relative_time("1 year ago") == "1 year ago"

    def test_parse_invalid(self):
        assert parse_relative_time("") is None
        assert parse_relative_time(None) is None


class TestFormatNumber:
    def test_format_small(self):
        assert format_number(500) == "500"
        assert format_number(999) == "999"

    def test_format_k(self):
        assert format_number(1500) == "1.5k"
        assert format_number(10000) == "10.0k"
        assert format_number(999999) == "1000.0k"

    def test_format_m(self):
        assert format_number(1_500_000) == "1.5M"
        assert format_number(10_000_000) == "10.0M"

    def test_format_none(self):
        assert format_number(None) == "N/A"


class TestTruncateText:
    def test_truncate_short(self):
        assert truncate_text("Hello", 10) == "Hello"

    def test_truncate_long(self):
        assert truncate_text("Hello World", 8) == "Hello..."

    def test_truncate_empty(self):
        assert truncate_text("", 10) == ""
        assert truncate_text(None, 10) == ""


class TestValidateGitHubURL:
    def test_valid_urls(self):
        assert validate_github_url("https://github.com/user/repo") is True
        assert validate_github_url("https://github.com/user") is True
        assert validate_github_url("http://github.com/user/repo") is True
        assert validate_github_url("https://www.github.com/user/repo") is True

    def test_invalid_urls(self):
        assert validate_github_url("https://gitlab.com/user/repo") is False
        assert validate_github_url("not-a-url") is False
        assert validate_github_url("") is False
        assert validate_github_url(None) is False


class TestParseLanguageColor:
    def test_parse_color(self):
        assert parse_language_color("background-color: #ff0000") == "#ff0000"
        assert parse_language_color("background-color:#00ff00") == "#00ff00"

    def test_parse_no_color(self):
        assert parse_language_color("color: red") == ""
        assert parse_language_color("") == ""
        assert parse_language_color(None) == ""