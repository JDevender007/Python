"""
Currency Converter API - Unit Tests for Exporter
"""

import pytest
import csv
import json
from pathlib import Path
from datetime import datetime
from src.exporter import CurrencyExporter, create_exporter
from src.models import ExchangeRatesResponse, ConversionResult


class TestCurrencyExporter:
    @pytest.fixture
    def exporter(self, tmp_path):
        return create_exporter(tmp_path)

    @pytest.fixture
    def sample_rates(self):
        return ExchangeRatesResponse(
            base="USD",
            rates={"EUR": 0.9234, "GBP": 0.7856, "JPY": 149.50},
            timestamp=1705315200,
            date="2024-01-15",
            source="primary"
        )

    @pytest.fixture
    def sample_conversion(self):
        return ConversionResult(
            from_currency="USD",
            to_currency="EUR",
            amount=100.0,
            result=92.34,
            rate=0.9234,
            timestamp=1705315200,
            source="primary"
        )

    @pytest.fixture
    def sample_history(self):
        return [
            {
                "timestamp": "2024-01-15T10:30:00",
                "from_currency": "USD",
                "to_currency": "EUR",
                "amount": 100.0,
                "result": 92.34,
                "rate": 0.9234
            },
            {
                "timestamp": "2024-01-15T11:00:00",
                "from_currency": "GBP",
                "to_currency": "USD",
                "amount": 50.0,
                "result": 63.50,
                "rate": 1.27
            }
        ]

    def test_export_conversion_csv(self, exporter, sample_conversion):
        filepath = exporter.export_conversion(sample_conversion)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0] == ["Field", "Value"]
        assert ["From Currency", "USD"] in rows
        assert ["To Currency", "EUR"] in rows
        assert ["Amount", "100.0"] in rows
        assert ["Result", "92.34"] in rows
        assert ["Exchange Rate", "0.9234"] in rows

    def test_export_rates_csv(self, exporter, sample_rates):
        filepath = exporter.export_rates(sample_rates)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Check header
        assert rows[0] == ["Base Currency", "USD"]
        # Check rates rows
        rate_rows = [r for r in rows if len(r) == 2 and r[0] in ["EUR", "GBP", "JPY"]]
        assert len(rate_rows) == 3

    def test_export_history_csv(self, exporter, sample_history):
        filepath = exporter.export_history(sample_history)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0] == ["Timestamp", "From Currency", "To Currency", "Amount", "Result", "Rate"]
        assert len(rows) == 3  # header + 2 entries

    def test_export_conversion_json(self, exporter, sample_conversion):
        filepath = exporter.export_conversion_json(sample_conversion)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["conversion"]["from_currency"] == "USD"
        assert data["conversion"]["to_currency"] == "EUR"
        assert data["conversion"]["amount"] == 100.0
        assert data["conversion"]["result"] == 92.34
        assert "exported_at" in data

    def test_export_rates_json(self, exporter, sample_rates):
        filepath = exporter.export_rates_json(sample_rates)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["base_currency"] == "USD"
        assert data["total_currencies"] == 3
        assert data["rates"]["EUR"] == 0.9234
        assert "exported_at" in data

    def test_export_history_json(self, exporter, sample_history):
        filepath = exporter.export_history_json(sample_history)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_entries"] == 2
        assert len(data["history"]) == 2
        assert "exported_at" in data

    def test_export_empty_conversion(self, exporter):
        csv_path = exporter.export_conversion(None)
        json_path = exporter.export_conversion_json(None)
        assert csv_path is None
        assert json_path is None

    def test_export_empty_rates(self, exporter):
        empty_rates = ExchangeRatesResponse(base="USD", rates={}, timestamp=0, date="", source="test")
        csv_path = exporter.export_rates(empty_rates)
        json_path = exporter.export_rates_json(empty_rates)
        assert csv_path is None
        assert json_path is None

    def test_export_empty_history(self, exporter):
        csv_path = exporter.export_history([])
        json_path = exporter.export_history_json([])
        assert csv_path is None
        assert json_path is None