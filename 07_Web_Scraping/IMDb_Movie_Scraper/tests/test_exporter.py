"""
IMDb Movie Scraper - Unit Tests for Exporter
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
    def sample_movies(self):
        return [
            {
                "rank": 1,
                "title": "The Shawshank Redemption",
                "year": 1994,
                "rating": 9.3,
                "votes": 2500000,
                "genres": ["Drama"],
                "duration_minutes": 142,
                "director": "Frank Darabont",
                "writers": ["Stephen King", "Frank Darabont"],
                "stars": ["Tim Robbins", "Morgan Freeman"],
                "description": "Two imprisoned men bond over a number of years.",
                "certificate": "R",
                "release_date": "September 23, 1994",
                "countries": ["United States"],
                "languages": ["English"],
                "budget": "$25,000,000",
                "gross": "$58,300,000",
                "poster_url": "https://example.com/poster.jpg",
                "url": "/title/tt0111161/",
            },
            {
                "rank": 2,
                "title": "The Godfather",
                "year": 1972,
                "rating": 9.2,
                "votes": 1800000,
                "genres": ["Crime", "Drama"],
                "duration_minutes": 175,
                "director": "Francis Ford Coppola",
                "writers": ["Mario Puzo", "Francis Ford Coppola"],
                "stars": ["Marlon Brando", "Al Pacino"],
                "description": "The aging patriarch of an organized crime dynasty transfers control.",
                "certificate": "R",
                "release_date": "March 24, 1972",
                "countries": ["United States"],
                "languages": ["English", "Italian"],
                "budget": "$6,000,000",
                "gross": "$287,000,000",
                "poster_url": "https://example.com/godfather.jpg",
                "url": "/title/tt0068646/",
            },
        ]

    def test_export_csv(self, exporter, sample_movies, tmp_path):
        filepath = exporter.export_csv(sample_movies, "test.csv")

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["title"] == "The Shawshank Redemption"
        assert rows[1]["title"] == "The Godfather"
        assert rows[0]["genres"] == "Drama"
        assert rows[1]["genres"] == "Crime; Drama"
        assert rows[0]["writers"] == "Stephen King; Frank Darabont"

    def test_export_json(self, exporter, sample_movies, tmp_path):
        filepath = exporter.export_json(sample_movies, "test.json")

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_movies"] == 2
        assert len(data["movies"]) == 2
        assert data["movies"][0]["title"] == "The Shawshank Redemption"
        assert data["movies"][1]["title"] == "The Godfather"
        assert data["movies"][0]["genres"] == "Drama"
        assert data["movies"][1]["genres"] == "Crime; Drama"
        assert "exported_at" in data

    def test_export_empty_list(self, exporter, tmp_path):
        csv_path = exporter.export_csv([], "empty.csv")
        json_path = exporter.export_json([], "empty.json")

        assert csv_path is None
        assert json_path is None

    def test_export_none_movies(self, exporter, tmp_path):
        csv_path = exporter.export_csv(None, "none.csv")
        json_path = exporter.export_json(None, "none.json")

        assert csv_path is None
        assert json_path is None

    def test_flatten_movie(self, exporter):
        movie = {
            "title": "Test",
            "genres": ["Action", "Adventure"],
            "nested": {"key": "value"},
            "simple": 123,
        }

        flat = exporter._flatten_movie(movie)

        assert flat["title"] == "Test"
        assert flat["genres"] == "Action; Adventure"
        assert flat["nested"] == '{"key": "value"}'
        assert flat["simple"] == 123