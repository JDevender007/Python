"""
Currency Converter API - Unit Tests for Models
"""

import pytest
from src.models import (
    ExchangeRate, ExchangeRatesResponse, ConversionResult,
    CurrencyInfo, parse_exchange_rates, parse_pair_rate, create_conversion_result
)


class TestDataClasses:
    def test_exchange_rate(self):
        rate = ExchangeRate(base="USD", target="EUR", rate=0.9234, timestamp=1705315200, source="primary")
        assert rate.base == "USD"
        assert rate.target == "EUR"
        assert rate.rate == 0.9234
        assert rate.formatted_rate == "0.923400"

    def test_exchange_rate_high(self):
        rate = ExchangeRate(base="EUR", target="JPY", rate=160.5, timestamp=1705315200)
        assert rate.formatted_rate == "160.5000"

    def test_exchange_rates_response(self):
        response = ExchangeRatesResponse(
            base="USD",
            rates={"EUR": 0.9234, "GBP": 0.7856, "JPY": 149.50},
            timestamp=1705315200,
            date="2024-01-15",
            source="primary"
        )
        assert response.base == "USD"
        assert response.get_rate("EUR") == 0.9234
        assert response.get_rate("eur") == 0.9234
        assert response.get_rate("XYZ") is None
        assert "EUR" in response.get_all_currencies()
        assert "GBP" in response.get_all_currencies()
        assert "JPY" in response.get_all_currencies()
        assert len(response.get_all_currencies()) == 3

    def test_conversion_result(self):
        result = ConversionResult(
            from_currency="USD",
            to_currency="EUR",
            amount=100.0,
            result=92.34,
            rate=0.9234,
            timestamp=1705315200,
            source="primary"
        )
        assert result.from_currency == "USD"
        assert result.to_currency == "EUR"
        assert result.amount == 100.0
        assert result.result == 92.34
        assert result.rate == 0.9234

    def test_currency_info(self):
        info = CurrencyInfo(code="USD", name="US Dollar", symbol="$")
        assert info.display == "USD - US Dollar ($)"


class TestParsers:
    def test_parse_exchange_rates(self):
        data = {
            "base": "USD",
            "rates": {"EUR": 0.9234, "GBP": 0.7856},
            "timestamp": 1705315200,
            "date": "2024-01-15",
            "source": "primary"
        }
        response = parse_exchange_rates(data)
        assert response is not None
        assert response.base == "USD"
        assert response.rates["EUR"] == 0.9234

    def test_parse_exchange_rates_invalid(self):
        data = {"invalid": "data"}
        response = parse_exchange_rates(data)
        # Should still parse with defaults
        assert response is not None

    def test_parse_pair_rate(self):
        data = {
            "base": "USD",
            "target": "EUR",
            "rate": 0.9234,
            "timestamp": 1705315200,
            "source": "primary"
        }
        rate = parse_pair_rate(data)
        assert rate is not None
        assert rate.base == "USD"
        assert rate.target == "EUR"
        assert rate.rate == 0.9234

    def test_parse_pair_rate_invalid(self):
        data = {"invalid": "data"}
        rate = parse_pair_rate(data)
        assert rate is not None  # Defaults to empty/zero

    def test_create_conversion_result(self):
        result = create_conversion_result("USD", "EUR", 100.0, 0.9234, 1705315200, "primary")
        assert result.from_currency == "USD"
        assert result.to_currency == "EUR"
        assert result.amount == 100.0
        assert result.result == 92.34
        assert result.rate == 0.9234

    def test_create_conversion_result_same_currency(self):
        result = create_conversion_result("USD", "USD", 100.0, 1.0, 1705315200, "same_currency")
        assert result.result == 100.0