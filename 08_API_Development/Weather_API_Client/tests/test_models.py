"""
Weather API Client - Unit Tests for Models
"""

import pytest
from src.models import (
    Coordinates, WeatherCondition, MainWeather, Wind, Clouds, Sys,
    CurrentWeather, ForecastItem, ForecastData, GeocodingResult,
    parse_current_weather, parse_forecast, parse_geocoding
)


class TestDataClasses:
    def test_coordinates(self):
        coord = Coordinates(lat=51.5074, lon=-0.1278)
        assert coord.lat == 51.5074
        assert coord.lon == -0.1278

    def test_weather_condition(self):
        wc = WeatherCondition(id=800, main="Clear", description="clear sky", icon="01d")
        assert wc.id == 800
        assert wc.main == "Clear"

    def test_main_weather(self):
        main = MainWeather(
            temp=20.5, feels_like=19.8, temp_min=18.0, temp_max=22.0,
            pressure=1013, humidity=65
        )
        assert main.temp == 20.5
        assert main.humidity == 65

    def test_wind(self):
        wind = Wind(speed=5.5, deg=180, gust=8.0)
        assert wind.speed == 5.5
        assert wind.gust == 8.0

    def test_geocoding_result(self):
        geo = GeocodingResult(name="London", country="GB", lat=51.5074, lon=-0.1278)
        assert geo.display_name == "London, GB"

    def test_geocoding_result_with_state(self):
        geo = GeocodingResult(name="New York", state="NY", country="US", lat=40.7128, lon=-74.0060)
        assert geo.display_name == "New York, NY, US"


class TestParseCurrentWeather:
    @pytest.fixture
    def sample_weather_data(self):
        return {
            "coord": {"lat": 51.5074, "lon": -0.1278},
            "weather": [
                {"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}
            ],
            "base": "stations",
            "main": {
                "temp": 15.5,
                "feels_like": 14.8,
                "temp_min": 13.0,
                "temp_max": 17.0,
                "pressure": 1013,
                "humidity": 65,
                "sea_level": 1013,
                "grnd_level": 1005
            },
            "visibility": 10000,
            "wind": {"speed": 4.5, "deg": 230, "gust": 7.0},
            "clouds": {"all": 0},
            "dt": 1705315200,
            "sys": {
                "country": "GB",
                "sunrise": 1705298400,
                "sunset": 1705327200,
                "type": 2,
                "id": 12345
            },
            "timezone": 0,
            "id": 2643743,
            "name": "London",
            "cod": 200
        }

    def test_parse_current_weather(self, sample_weather_data):
        weather = parse_current_weather(sample_weather_data)

        assert weather is not None
        assert weather.name == "London"
        assert weather.sys.country == "GB"
        assert weather.coord.lat == 51.5074
        assert weather.coord.lon == -0.1278
        assert weather.main.temp == 15.5
        assert weather.main.feels_like == 14.8
        assert weather.main.humidity == 65
        assert weather.main.pressure == 1013
        assert weather.wind.speed == 4.5
        assert weather.wind.deg == 230
        assert weather.wind.gust == 7.0
        assert weather.clouds.all == 0
        assert weather.visibility == 10000
        assert weather.primary_condition.main == "Clear"
        assert weather.primary_condition.description == "clear sky"
        assert weather.condition_description == "Clear sky"

    def test_parse_current_weather_minimal(self):
        minimal_data = {
            "coord": {"lat": 0, "lon": 0},
            "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
            "base": "stations",
            "main": {"temp": 20, "feels_like": 20, "temp_min": 20, "temp_max": 20, "pressure": 1013, "humidity": 50},
            "visibility": 10000,
            "wind": {"speed": 0, "deg": 0},
            "clouds": {"all": 0},
            "dt": 1705315200,
            "sys": {"country": "XX", "sunrise": 0, "sunset": 0},
            "timezone": 0,
            "id": 0,
            "name": "Test",
            "cod": 200
        }
        weather = parse_current_weather(minimal_data)
        assert weather is not None
        assert weather.name == "Test"


class TestParseForecast:
    @pytest.fixture
    def sample_forecast_data(self):
        return {
            "cod": "200",
            "message": 0,
            "cnt": 2,
            "list": [
                {
                    "dt": 1705315200,
                    "main": {
                        "temp": 15.5,
                        "feels_like": 14.8,
                        "temp_min": 13.0,
                        "temp_max": 17.0,
                        "pressure": 1013,
                        "humidity": 65
                    },
                    "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
                    "clouds": {"all": 0},
                    "wind": {"speed": 4.5, "deg": 230},
                    "visibility": 10000,
                    "pop": 0,
                    "sys": {"pod": "d"},
                    "dt_txt": "2024-01-15 12:00:00"
                },
                {
                    "dt": 1705326000,
                    "main": {
                        "temp": 13.0,
                        "feels_like": 12.5,
                        "temp_min": 11.0,
                        "temp_max": 14.0,
                        "pressure": 1015,
                        "humidity": 70
                    },
                    "weather": [{"id": 500, "main": "Rain", "description": "light rain", "icon": "10d"}],
                    "clouds": {"all": 100},
                    "wind": {"speed": 6.0, "deg": 250},
                    "visibility": 8000,
                    "pop": 0.8,
                    "sys": {"pod": "d"},
                    "dt_txt": "2024-01-15 15:00:00"
                }
            ],
            "city": {
                "id": 2643743,
                "name": "London",
                "coord": {"lat": 51.5074, "lon": -0.1278},
                "country": "GB",
                "population": 1000000,
                "timezone": 0,
                "sunrise": 1705298400,
                "sunset": 1705327200
            }
        }

    def test_parse_forecast(self, sample_forecast_data):
        forecast = parse_forecast(sample_forecast_data)

        assert forecast is not None
        assert forecast.cod == "200"
        assert forecast.cnt == 2
        assert len(forecast.list) == 2

        item1 = forecast.list[0]
        assert item1.main.temp == 15.5
        assert item1.primary_condition.main == "Clear"
        assert item1.pop == 0

        item2 = forecast.list[1]
        assert item2.main.temp == 13.0
        assert item2.primary_condition.main == "Rain"
        assert item2.pop == 0.8

        assert forecast.city["name"] == "London"
        assert forecast.city["country"] == "GB"


class TestParseGeocoding:
    @pytest.fixture
    def sample_geocoding_data(self):
        return [
            {
                "name": "London",
                "local_names": {"en": "London", "fr": "Londres"},
                "lat": 51.5074,
                "lon": -0.1278,
                "country": "GB",
                "state": ""
            },
            {
                "name": "London",
                "local_names": {"en": "London"},
                "lat": 42.9849,
                "lon": -81.2453,
                "country": "CA",
                "state": "Ontario"
            }
        ]

    def test_parse_geocoding(self, sample_geocoding_data):
        results = parse_geocoding(sample_geocoding_data)

        assert len(results) == 2
        assert results[0].name == "London"
        assert results[0].country == "GB"
        assert results[0].lat == 51.5074
        assert results[0].lon == -0.1278

        assert results[1].name == "London"
        assert results[1].country == "CA"
        assert results[1].state == "Ontario"
        assert results[1].lat == 42.9849
        assert results[1].lon == -81.2453

    def test_parse_geocoding_empty(self):
        results = parse_geocoding([])
        assert results == []