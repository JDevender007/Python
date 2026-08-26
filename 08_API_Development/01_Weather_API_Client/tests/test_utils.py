"""
Weather API Client - Unit Tests for Utils
"""

import pytest
from datetime import datetime, timezone
from src.utils import (
    clean_text,
    kelvin_to_celsius,
    kelvin_to_fahrenheit,
    celsius_to_fahrenheit,
    format_temperature,
    format_wind_speed,
    format_pressure,
    format_humidity,
    format_visibility,
    unix_to_datetime,
    format_datetime,
    format_sun_time,
    get_weather_icon,
    get_temp_color,
    wind_deg_to_direction,
    validate_city_name,
    parse_city_input,
    format_number,
)


class TestCleanText:
    def test_clean_text_normal(self):
        assert clean_text("  Hello   World  ") == "Hello World"

    def test_clean_text_newlines(self):
        assert clean_text("Hello\n\nWorld") == "Hello World"

    def test_clean_text_empty(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""


class TestTemperatureConversions:
    def test_kelvin_to_celsius(self):
        assert kelvin_to_celsius(273.15) == 0.0
        assert kelvin_to_celsius(300.15) == 27.0
        assert kelvin_to_celsius(255.37) == -17.8

    def test_kelvin_to_fahrenheit(self):
        assert kelvin_to_fahrenheit(273.15) == 32.0
        assert kelvin_to_fahrenheit(300.15) == 80.6

    def test_celsius_to_fahrenheit(self):
        assert celsius_to_fahrenheit(0) == 32.0
        assert celsius_to_fahrenheit(100) == 212.0
        assert celsius_to_fahrenheit(-40) == -40.0


class TestFormatFunctions:
    def test_format_temperature(self):
        assert format_temperature(25.5, "metric") == "25.5°C"
        assert format_temperature(77.9, "imperial") == "77.9°F"

    def test_format_wind_speed(self):
        assert format_wind_speed(5.5, "metric") == "5.5 m/s"
        assert format_wind_speed(12.3, "imperial") == "12.3 mph"

    def test_format_pressure(self):
        assert format_pressure(1013) == "1013 hPa"

    def test_format_humidity(self):
        assert format_humidity(65) == "65%"

    def test_format_visibility(self):
        assert format_visibility(10000) == "10.0 km"
        assert format_visibility(500) == "500 m"


class TestDatetimeFunctions:
    def test_unix_to_datetime(self):
        dt = unix_to_datetime(1704067200)
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1

    def test_unix_to_datetime_with_offset(self):
        dt = unix_to_datetime(1704067200, 3600)
        assert dt.hour == 1

    def test_format_datetime(self):
        dt = datetime(2024, 1, 15, 14, 30)
        assert format_datetime(dt) == "2024-01-15 14:30"

    def test_format_sun_time(self):
        result = format_sun_time(1705305600, 0, "%H:%M")
        assert result == "08:00"


class TestWeatherIcons:
    def test_get_weather_icon_thunderstorm(self):
        assert get_weather_icon(200) == "⛈️"
        assert get_weather_icon(299) == "⛈️"

    def test_get_weather_icon_drizzle(self):
        assert get_weather_icon(300) == "🌦️"

    def test_get_weather_icon_rain(self):
        assert get_weather_icon(500) == "🌧️"

    def test_get_weather_icon_snow(self):
        assert get_weather_icon(600) == "❄️"

    def test_get_weather_icon_atmosphere(self):
        assert get_weather_icon(701) == "🌫️"

    def test_get_weather_icon_clear_day(self):
        assert get_weather_icon(800, True) == "☀️"

    def test_get_weather_icon_clear_night(self):
        assert get_weather_icon(800, False) == "🌙"

    def test_get_weather_icon_clouds(self):
        assert get_weather_icon(801) == "☁️"
        assert get_weather_icon(803) == "☁️"


class TestTempColor:
    def test_get_temp_color_cold(self):
        assert get_temp_color(-5, "metric") == "#89b4fa"
        assert get_temp_color(0, "metric") == "#89b4fa"

    def test_get_temp_color_cool(self):
        assert get_temp_color(10, "metric") == "#b4befe"
        assert get_temp_color(15, "metric") == "#b4befe"

    def test_get_temp_color_mild(self):
        assert get_temp_color(20, "metric") == "#f9e2af"
        assert get_temp_color(25, "metric") == "#f9e2af"

    def test_get_temp_color_warm(self):
        assert get_temp_color(28, "metric") == "#fab387"
        assert get_temp_color(32, "metric") == "#fab387"

    def test_get_temp_color_hot(self):
        assert get_temp_color(35, "metric") == "#f38ba8"

    def test_get_temp_color_imperial(self):
        assert get_temp_color(32, "imperial") == "#89b4fa"
        assert get_temp_color(86, "imperial") == "#fab387"


class TestWindDirection:
    def test_wind_deg_to_direction(self):
        assert wind_deg_to_direction(0) == "N"
        assert wind_deg_to_direction(45) == "NE"
        assert wind_deg_to_direction(90) == "E"
        assert wind_deg_to_direction(135) == "SE"
        assert wind_deg_to_direction(180) == "S"
        assert wind_deg_to_direction(225) == "SW"
        assert wind_deg_to_direction(270) == "W"
        assert wind_deg_to_direction(315) == "NW"
        assert wind_deg_to_direction(360) == "N"


class TestCityValidation:
    def test_validate_city_name_valid(self):
        assert validate_city_name("London") is True
        assert validate_city_name("New York") is True
        assert validate_city_name("St. Petersburg") is True

    def test_validate_city_name_invalid(self):
        assert validate_city_name("") is False
        assert validate_city_name("A") is False
        assert validate_city_name("123") is False
        assert validate_city_name("@#$") is False


class TestParseCityInput:
    def test_parse_city_with_country(self):
        result = parse_city_input("London,UK")
        assert result["city"] == "London"
        assert result["country"] == "UK"

    def test_parse_city_without_country(self):
        result = parse_city_input("Tokyo")
        assert result["city"] == "Tokyo"
        assert result["country"] == ""

    def test_parse_city_with_spaces(self):
        result = parse_city_input("New York, US")
        assert result["city"] == "New York"
        assert result["country"] == "US"


class TestFormatNumber:
    def test_format_number(self):
        assert format_number(25.567, 1) == "25.6"
        assert format_number(25.567, 2) == "25.57"
        assert format_number(None) == "N/A"