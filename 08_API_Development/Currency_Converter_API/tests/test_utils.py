"""
Currency Converter API - Unit Tests for Utils
"""

import pytest
from src.utils import (
    clean_text,
    format_currency,
    format_number,
    format_rate,
    format_percentage,
    validate_currency_code,
    validate_amount,
    get_currency_symbol,
    get_currency_name,
    timestamp_to_string,
)


class TestCleanText:
    def test_clean_text_normal(self):
        assert clean_text("  Hello   World  ") == "Hello World"

    def test_clean_text_newlines(self):
        assert clean_text("Hello\n\nWorld") == "Hello World"

    def test_clean_text_empty(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""


class TestFormatCurrency:
    def test_format_currency_usd(self):
        assert format_currency(1000.50, "USD") == "$1,000.50"
        assert format_currency(1000, "USD") == "$1,000.00"

    def test_format_currency_eur(self):
        assert format_currency(1000.50, "EUR") == "€1,000.50"

    def test_format_currency_jpy(self):
        assert format_currency(1000, "JPY") == "¥1,000"

    def test_format_currency_inr(self):
        assert format_currency(1000.50, "INR") == "₹1,000.50"

    def test_format_currency_unknown(self):
        assert format_currency(1000, "XYZ") == "XYZ1,000.00"


class TestFormatNumber:
    def test_format_number(self):
        assert format_number(1234.5678, 2) == "1,234.57"
        assert format_number(1234.5678, 4) == "1,234.5678"
        assert format_number(1000000, 2) == "1,000,000.00"

    def test_format_number_none(self):
        assert format_number(None) == "N/A"


class TestFormatRate:
    def test_format_rate_gte_1(self):
        assert format_rate(1.2345) == "1.2345"
        assert format_rate(100.0) == "100.0000"

    def test_format_rate_lt_1(self):
        assert format_rate(0.5) == "0.500000"
        assert format_rate(0.01) == "0.010000"

    def test_format_rate_very_small(self):
        assert format_rate(0.001) == "0.00100000"
        assert format_rate(0.0001) == "0.00010000"


class TestFormatPercentage:
    def test_format_percentage(self):
        assert format_percentage(12.345) == "12.35%"
        assert format_percentage(100) == "100.00%"
        assert format_percentage(0.5) == "0.50%"


class TestValidateCurrencyCode:
    def test_valid_codes(self):
        assert validate_currency_code("USD") is True
        assert validate_currency_code("eur") is True
        assert validate_currency_code("Gbp") is True
        assert validate_currency_code("JPY") is True

    def test_invalid_codes(self):
        assert validate_currency_code("US") is False
        assert validate_currency_code("USDD") is False
        assert validate_currency_code("123") is False
        assert validate_currency_code("US$") is False
        assert validate_currency_code("") is False
        assert validate_currency_code(None) is False


class TestValidateAmount:
    def test_valid_amounts(self):
        assert validate_amount("100") == 100.0
        assert validate_amount("100.50") == 100.50
        assert validate_amount("1,000.50") == 1000.50
        assert validate_amount("$100") == 100.0
        assert validate_amount("€1,000.50") == 1000.50

    def test_invalid_amounts(self):
        assert validate_amount("") is None
        assert validate_amount("abc") is None
        assert validate_amount("-100") is None
        assert validate_amount(None) is None


class TestCurrencySymbols:
    def test_get_currency_symbol(self):
        assert get_currency_symbol("USD") == "$"
        assert get_currency_symbol("EUR") == "€"
        assert get_currency_symbol("GBP") == "£"
        assert get_currency_symbol("JPY") == "¥"
        assert get_currency_symbol("INR") == "₹"
        assert get_currency_symbol("XYZ") == "XYZ"

    def test_get_currency_name(self):
        assert get_currency_name("USD") == "US Dollar"
        assert get_currency_name("EUR") == "Euro"
        assert get_currency_name("GBP") == "British Pound"
        assert get_currency_name("JPY") == "Japanese Yen"
        assert get_currency_name("XYZ") == "XYZ"


class TestTimestampToString:
    def test_timestamp_to_string(self):
        result = timestamp_to_string("2024-01-15T10:30:00")
        assert "2024-01-15" in result
        assert "10:30:00" in result

    def test_timestamp_to_string_with_z(self):
        result = timestamp_to_string("2024-01-15T10:30:00Z")
        assert "2024-01-15" in result

    def test_timestamp_to_string_invalid(self):
        result = timestamp_to_string("invalid")
        assert result == "invalid"