"""
Weather API Client - Exporter Module
Handles exporting weather data to CSV and JSON.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from .config import EXPORTS_DIR
from .logger import logger
from .models import ForecastData


class WeatherExporter:
    """Handles exporting weather data."""

    def __init__(self, export_dir: Path = EXPORTS_DIR):
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_current_weather(self, weather, filename: str = None) -> Optional[Path]:
        """Export current weather to CSV."""
        if not weather:
            logger.warning("No weather data to export")
            return None

        filename = filename or f"weather_{weather.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Field", "Value"])
                writer.writerow(["City", weather.name])
                writer.writerow(["Country", weather.sys.country])
                writer.writerow(["Coordinates", f"{weather.coord.lat}, {weather.coord.lon}"])
                writer.writerow(["Temperature", f"{weather.main.temp}°C"])
                writer.writerow(["Feels Like", f"{weather.main.feels_like}°C"])
                writer.writerow(["Min Temperature", f"{weather.main.temp_min}°C"])
                writer.writerow(["Max Temperature", f"{weather.main.temp_max}°C"])
                writer.writerow(["Pressure", f"{weather.main.pressure} hPa"])
                writer.writerow(["Humidity", f"{weather.main.humidity}%"])
                writer.writerow(["Visibility", f"{weather.visibility} m"])
                writer.writerow(["Wind Speed", f"{weather.wind.speed} m/s"])
                writer.writerow(["Wind Direction", f"{weather.wind.deg}°"])
                writer.writerow(["Cloud Coverage", f"{weather.clouds.all}%"])
                writer.writerow(["Weather", weather.condition_description])
                writer.writerow(["Sunrise", datetime.fromtimestamp(weather.sys.sunrise).strftime("%H:%M")])
                writer.writerow(["Sunset", datetime.fromtimestamp(weather.sys.sunset).strftime("%H:%M")])
                writer.writerow(["Timezone Offset", f"{weather.timezone} seconds"])
                writer.writerow(["Data Timestamp", datetime.fromtimestamp(weather.dt).strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow(["Exported At", datetime.now().isoformat()])

            logger.info(f"Exported current weather to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting current weather to CSV: {e}")
            return None

    def export_forecast(self, forecast: ForecastData, filename: str = None) -> Optional[Path]:
        """Export forecast to CSV."""
        if not forecast or not forecast.list:
            logger.warning("No forecast data to export")
            return None

        city_name = forecast.city.get("name", "unknown")
        filename = filename or f"forecast_{city_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Date", "Time", "Temperature", "Feels Like", "Min Temp", "Max Temp",
                    "Pressure", "Humidity", "Weather", "Description", "Wind Speed",
                    "Wind Direction", "Clouds", "Precipitation Probability"
                ])

                for item in forecast.list:
                    dt = datetime.fromtimestamp(item.dt)
                    condition = item.primary_condition
                    writer.writerow([
                        dt.strftime("%Y-%m-%d"),
                        dt.strftime("%H:%M"),
                        f"{item.main.temp}°C",
                        f"{item.main.feels_like}°C",
                        f"{item.main.temp_min}°C",
                        f"{item.main.temp_max}°C",
                        f"{item.main.pressure} hPa",
                        f"{item.main.humidity}%",
                        condition.main if condition else "N/A",
                        condition.description if condition else "N/A",
                        f"{item.wind.speed} m/s",
                        f"{item.wind.deg}°",
                        f"{item.clouds.all}%",
                        f"{int(item.pop * 100)}%"
                    ])

            logger.info(f"Exported forecast to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting forecast to CSV: {e}")
            return None

    def export_search_results(self, results: List, filename: str = None) -> Optional[Path]:
        """Export city search results to CSV."""
        if not results:
            logger.warning("No search results to export")
            return None

        filename = filename or f"city_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Name", "Country", "State", "Latitude", "Longitude"])

                for result in results:
                    writer.writerow([
                        result.name,
                        result.country,
                        result.state or "",
                        result.lat,
                        result.lon
                    ])

            logger.info(f"Exported search results to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting search results to CSV: {e}")
            return None

    def export_current_weather_json(self, weather, filename: str = None) -> Optional[Path]:
        """Export current weather to JSON."""
        if not weather:
            logger.warning("No weather data to export")
            return None

        filename = filename or f"weather_{weather.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.export_dir / filename

        try:
            data = {
                "exported_at": datetime.now().isoformat(),
                "city": weather.name,
                "country": weather.sys.country,
                "coordinates": {"lat": weather.coord.lat, "lon": weather.coord.lon},
                "temperature": weather.main.temp,
                "feels_like": weather.main.feels_like,
                "temp_min": weather.main.temp_min,
                "temp_max": weather.main.temp_max,
                "pressure": weather.main.pressure,
                "humidity": weather.main.humidity,
                "visibility": weather.visibility,
                "wind": {"speed": weather.wind.speed, "deg": weather.wind.deg, "gust": weather.wind.gust},
                "clouds": weather.clouds.all,
                "weather": {
                    "main": weather.primary_condition.main,
                    "description": weather.primary_condition.description,
                    "icon": weather.primary_condition.icon
                } if weather.primary_condition else None,
                "sunrise": datetime.fromtimestamp(weather.sys.sunrise).isoformat(),
                "sunset": datetime.fromtimestamp(weather.sys.sunset).isoformat(),
                "timezone": weather.timezone,
                "dt": datetime.fromtimestamp(weather.dt).isoformat()
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported current weather to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting current weather to JSON: {e}")
            return None

    def export_forecast_json(self, forecast: ForecastData, filename: str = None) -> Optional[Path]:
        """Export forecast to JSON."""
        if not forecast or not forecast.list:
            logger.warning("No forecast data to export")
            return None

        city_name = forecast.city.get("name", "unknown")
        filename = filename or f"forecast_{city_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.export_dir / filename

        try:
            forecast_items = []
            for item in forecast.list:
                condition = item.primary_condition
                forecast_items.append({
                    "dt": datetime.fromtimestamp(item.dt).isoformat(),
                    "temperature": item.main.temp,
                    "feels_like": item.main.feels_like,
                    "temp_min": item.main.temp_min,
                    "temp_max": item.main.temp_max,
                    "pressure": item.main.pressure,
                    "humidity": item.main.humidity,
                    "weather": {
                        "main": condition.main,
                        "description": condition.description,
                        "icon": condition.icon
                    } if condition else None,
                    "wind": {"speed": item.wind.speed, "deg": item.wind.deg, "gust": item.wind.gust},
                    "clouds": item.clouds.all,
                    "pop": item.pop
                })

            data = {
                "exported_at": datetime.now().isoformat(),
                "city": forecast.city.get("name"),
                "country": forecast.city.get("country"),
                "coordinates": forecast.city.get("coord"),
                "timezone": forecast.city.get("timezone"),
                "forecast": forecast_items
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported forecast to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting forecast to JSON: {e}")
            return None


def create_exporter(export_dir: Path = None) -> WeatherExporter:
    """Factory function to create exporter."""
    return WeatherExporter(export_dir) if export_dir else WeatherExporter()