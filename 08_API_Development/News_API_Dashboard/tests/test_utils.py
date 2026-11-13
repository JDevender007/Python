"""
News API Dashboard - Unit Tests for Utils
"""

import pytest
from src.utils import (
    clean_text,
    format_number,
    format_date,
    format_datetime,
    format_relative_time,
    truncate_text,
    extract_domain,
    calculate_reading_time,
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


class TestFormatRelativeTime:
    def test_format_relative_time_recent(self):
        # Should return something like "Just now" or "X minutes ago"
        result = format_relative_time("2024-01-15T10:30:00Z")
        assert isinstance(result, str)

    def test_format_relative_time_invalid(self):
        assert format_relative_time("invalid") == "N/A"
        assert format_relative_time("") == "N/A"
        assert format_relative_time(None) == "N/A"


class TestTruncateText:
    def test_truncate_short(self):
        assert truncate_text("Hello", 10) == "Hello"

    def test_truncate_long(self):
        assert truncate_text("Hello World", 8) == "Hello..."

    def test_truncate_empty(self):
        assert truncate_text("", 10) == ""
        assert truncate_text(None, 10) == ""


class TestExtractDomain:
    def test_extract_domain(self):
        assert extract_domain("https://www.example.com/article") == "example.com"
        assert extract_domain("http://example.com/path") == "example.com"
        assert extract_domain("https://sub.domain.com") == "sub.domain.com"

    def test_extract_domain_invalid(self):
        assert extract_domain("") == ""
        assert extract_domain(None) == ""


class TestCalculateReadingTime:
    def test_calculate_reading_time(self):
        text = " ".join(["word"] * 200)
        result = calculate_reading_time(text)
        assert "1 min read" in result

    def test_calculate_reading_time_long(self):
        text = " ".join(["word"] * 500)
        result = calculate_reading_time(text)
        assert "3 min read" in result

    def test_calculate_reading_time_empty(self):
        assert calculate_reading_time("") == "0 min"
        assert calculate_reading_time(None) == "0 min"