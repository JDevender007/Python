"""
IMDb Movie Scraper - Unit Tests for Utils
"""

import pytest
from src.utils import (
    clean_text,
    extract_year,
    extract_rating,
    extract_votes,
    parse_duration,
    format_number,
    truncate_text,
    validate_url,
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


class TestExtractYear:
    def test_extract_year_parentheses(self):
        assert extract_year("(2023)") == 2023
        assert extract_year("(1999)") == 1999

    def test_extract_year_plain(self):
        assert extract_year("2023") == 2023

    def test_extract_year_in_text(self):
        assert extract_year("Released: 2023") == 2023

    def test_extract_year_invalid(self):
        assert extract_year("abc") is None
        assert extract_year("1800") is None
        assert extract_year("2100") is None
        assert extract_year("") is None
        assert extract_year(None) is None


class TestExtractRating:
    def test_extract_rating_normal(self):
        assert extract_rating("8.5") == 8.5
        assert extract_rating("9.0") == 9.0

    def test_extract_rating_in_text(self):
        assert extract_rating("Rating: 8.5/10") == 8.5

    def test_extract_rating_invalid(self):
        assert extract_rating("abc") is None
        assert extract_rating("11.0") is None
        assert extract_rating("-1.0") is None
        assert extract_rating("") is None
        assert extract_rating(None) is None


class TestExtractVotes:
    def test_extract_votes_plain(self):
        assert extract_votes("1000000") == 1_000_000
        assert extract_votes("1,000,000") == 1_000_000

    def test_extract_votes_with_suffix(self):
        assert extract_votes("1.5M") == 1_500_000
        assert extract_votes("500K") == 500_000
        assert extract_votes("2B") == 2_000_000_000

    def test_extract_votes_invalid(self):
        assert extract_votes("abc") is None
        assert extract_votes("") is None
        assert extract_votes(None) is None


class TestParseDuration:
    def test_parse_duration_hours_minutes(self):
        assert parse_duration("2h 30m") == 150
        assert parse_duration("1h 45m") == 105

    def test_parse_duration_hours_only(self):
        assert parse_duration("2h") == 120

    def test_parse_duration_minutes_only(self):
        assert parse_duration("90m") == 90

    def test_parse_duration_invalid(self):
        assert parse_duration("abc") is None
        assert parse_duration("") is None
        assert parse_duration(None) is None


class TestFormatNumber:
    def test_format_number_normal(self):
        assert format_number(1000) == "1,000"
        assert format_number(1_000_000) == "1,000,000"

    def test_format_number_none(self):
        assert format_number(None) == "N/A"


class TestTruncateText:
    def test_truncate_short(self):
        assert truncate_text("Hello", 10) == "Hello"

    def test_truncate_long(self):
        assert truncate_text("Hello World", 8) == "Hello..."

    def test_truncate_empty(self):
        assert truncate_text("", 10) == ""
        assert truncate_text(None, 10) == ""


class TestValidateURL:
    def test_valid_urls(self):
        assert validate_url("https://www.imdb.com/chart/top/") is True
        assert validate_url("http://example.com") is True
        assert validate_url("https://sub.domain.com/path") is True

    def test_invalid_urls(self):
        assert validate_url("not-a-url") is False
        assert validate_url("") is False
        assert validate_url(None) is False
        assert validate_url("ftp://example.com") is False