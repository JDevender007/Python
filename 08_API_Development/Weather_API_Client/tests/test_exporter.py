"""
Weather API Client - Unit Tests for Exporter
"""

import pytest
import csv
import json
from pathlib import Path
from datetime import datetime
from src.exporter import WeatherExporter, create_exporter
from src.models import (
    Coordinates, WeatherCondition, MainWeather, Wind, Clouds, Sys,
    CurrentWeather, ForecastItem, ForecastData
)


class TestWeatherExporter:
    @pytest.fixture
    def exporter(self, tmp_path):
        return create_exporter(tmp_path)

    @pytest.fixture
    def sample_weather(self):
        coord = Coordinates(lat=51.5074, lon=-0.1278)
        weather_cond = WeatherCondition(id=800, main="Clear", description="clear sky", icon="01d")
        main = MainWeather(temp=15.5, feels_like=14.8, temp_min=13.0, temp_max=17.0, pressure=1013, humidity=65)
        wind = Wind(speed=4.5, deg=230, gust=7.0)
        clouds = Clouds(all=0)
        sys = Sys(country="GB", sunrise=1705298400, sunset=1705327200)

        return CurrentWeather(
            coord=coord,
            weather=[weather_cond],
            base="stations",
            main=main,
            visibility=10000,
            wind=wind,
            clouds=clouds,
            dt=1705315200,
            sys=sys,
            timezone=0,
            id=2643743,
            name="London",
            cod=200
        )

    @pytest.fixture
    def sample_forecast(self):
        coord = Coordinates(lat=51.5074, lon=-0.1278)
        weather1 = WeatherCondition(id=800, main="Clear", description="clear sky", icon="01d")
        main1 = MainWeather(temp=15.5, feels_like=14.8, temp_min=13.0, temp_max=17.0, pressure=1013, humidity=65)
        wind1 = Wind(speed=4.5, deg=230)
        clouds1 = Clouds(all=0)
        sys1 = Sys(country="GB", sunrise=0, sunset=0)

        weather2 = WeatherCondition(id=500, main="Rain", description="light rain", icon="10d")
        main2 = MainWeather(temp=13.0, feels_like=12.5, temp_min=11.0, temp_max=14.0, pressure=1015, humidity=70)
        wind2 = Wind(speed=6.0, deg=250)
        clouds2 = Clouds(all=100)

        item1 = ForecastItem(
            dt=1705315200, main=main1, weather=[weather1], clouds=clouds1,
            wind=wind1, visibility=10000, pop=0, sys=sys1, dt_txt="2024-01-15 12:00:00"
        )
        item2 = ForecastItem(
            dt=1705326000, main=main2, weather=[weather2], clouds=clouds2,
            wind=wind2, visibility=8000, pop=0.8, sys=sys1, dt_txt="2024-01-15 15:00:00"
        )

        return ForecastData(
            cod="200", message=0, cnt=2, list=[item1, item2],
            city={"name": "London", "country": "GB", "coord": {"lat": 51.5074, "lon": -0.1278}, "timezone": 0}
        )

    def test_export_current_weather_csv(self, exporter, sample_weather):
        filepath = exporter.export_current_weather(sample_weather)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Check header
        assert rows[0] == ["Field", "Value"]
        # Check some values
        assert ["City", "London"] in rows
        assert ["Country", "GB"] in rows
        assert ["Temperature", "15.5°C"] in rows

    def test_export_forecast_csv(self, exporter, sample_forecast):
        filepath = exporter.export_forecast(sample_forecast)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Check header
        assert rows[0][0] == "Date"
        # Check data rows (2 forecast items)
        assert len(rows) == 3  # header + 2 items

    def test_export_current_weather_json(self, exporter, sample_weather):
        filepath = exporter.export_current_weather_json(sample_weather)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["city"] == "London"
        assert data["country"] == "GB"
        assert data["temperature"] == 15.5
        assert "exported_at" in data

    def test_export_forecast_json(self, exporter, sample_forecast):
        filepath = exporter.export_forecast_json(sample_forecast)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["city"] == "London"
        assert data["country"] == "GB"
        assert len(data["forecast"]) == 2
        assert "exported_at" in data

    def test_export_search_results_csv(self, exporter):
        from src.models import GeocodingResult
        results = [
            GeocodingResult(name="London", country="GB", lat=51.5074, lon=-0.1278),
            GeocodingResult(name="Paris", country="FR", lat=48.8566, lon=2.3522)
        ]

        filepath = exporter.export_search_results(results)

        assert filepath is not None
        assert filepath.exists()

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0] == ["Name", "Country", "State", "Latitude", "Longitude"]
        assert rows[1] == ["London", "GB", "", "51.5074", "-0.1278"]
        assert rows[2] == ["Paris", "FR", "", "48.8566", "2.3522"]

    def test_export_empty_weather(self, exporter):
        csv_path = exporter.export_current_weather(None)
        json_path = exporter.export_current_weather_json(None)
        assert csv_path is None
        assert json_path is None

    def test_export_empty_forecast(self, exporter):
        csv_path = exporter.export_forecast(None)
        json_path = exporter.export_forecast_json(None)
        assert csv_path is None
        assert json_path is None

    def test_export_empty_search(self, exporter):
        csv_path = exporter.export_search_results([])
        assert csv_path is None