"""
News API Dashboard - Unit Tests for Exporter
"""

import pytest
import csv
import json
from pathlib import Path
from datetime import datetime
from src.exporter import NewsExporter, create_exporter
from src.models import Article, Source


class TestNewsExporter:
    @pytest.fixture
    def exporter(self, tmp_path):
        return create_exporter(tmp_path)

    @pytest.fixture
    def sample_articles(self):
        return [
            Article(
                title="Test Article 1",
                description="Description 1",
                content="Full content 1",
                url="https://example.com/1",
                image_url="https://example.com/img1.jpg",
                source_name="Source 1",
                author="Author 1",
                published_at="2024-01-15T10:30:00Z",
                category="technology",
                country="us",
            ),
            Article(
                title="Test Article 2",
                description="Description 2",
                content="Full content 2",
                url="https://example.com/2",
                image_url="https://example.com/img2.jpg",
                source_name="Source 2",
                author="Author 2",
                published_at="2024-01-14T15:00:00Z",
                category="business",
                country="gb",
            ),
        ]

    @pytest.fixture
    def sample_sources(self):
        return [
            Source(
                id="src1",
                name="Source 1",
                description="First source",
                url="https://source1.com",
                category="technology",
                language="en",
                country="us",
            ),
            Source(
                id="src2",
                name="Source 2",
                description="Second source",
                url="https://source2.com",
                category="business",
                language="en",
                country="gb",
            ),
        ]

    def test_export_articles_csv(self, exporter, sample_articles):
        filepath = exporter.export_articles(sample_articles)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0][0] == "Title"
        assert len(rows) == 3  # header + 2 articles

    def test_export_sources_csv(self, exporter, sample_sources):
        filepath = exporter.export_sources(sample_sources)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0][0] == "ID"
        assert len(rows) == 3  # header + 2 sources

    def test_export_articles_json(self, exporter, sample_articles):
        filepath = exporter.export_articles_json(sample_articles)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_articles"] == 2
        assert len(data["articles"]) == 2
        assert data["articles"][0]["title"] == "Test Article 1"
        assert "exported_at" in data

    def test_export_sources_json(self, exporter, sample_sources):
        filepath = exporter.export_sources_json(sample_sources)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_sources"] == 2
        assert len(data["sources"]) == 2
        assert data["sources"][0]["id"] == "src1"
        assert "exported_at" in data

    def test_export_empty_articles(self, exporter):
        csv_path = exporter.export_articles([])
        json_path = exporter.export_articles_json([])
        assert csv_path is None
        assert json_path is None

    def test_export_empty_sources(self, exporter):
        csv_path = exporter.export_sources([])
        json_path = exporter.export_sources_json([])
        assert csv_path is None
        assert json_path is None