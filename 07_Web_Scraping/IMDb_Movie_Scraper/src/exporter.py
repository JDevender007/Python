"""
IMDb Movie Scraper - Exporter Module
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from .config import EXPORTS_DIR, CSV_FILENAME, JSON_FILENAME
from .logger import logger


class DataExporter:
    """Handles exporting movie data to various formats."""

    def __init__(self, export_dir: Path = EXPORTS_DIR):
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_csv(self, movies: List[Dict], filename: Optional[str] = None) -> Optional[Path]:
        """Export movies to CSV."""
        if not movies:
            logger.warning("No movies to export to CSV")
            return None

        filename = filename or CSV_FILENAME
        filepath = self.export_dir / filename

        fieldnames = [
            "rank",
            "title",
            "year",
            "rating",
            "votes",
            "genres",
            "duration_minutes",
            "director",
            "writers",
            "stars",
            "description",
            "certificate",
            "release_date",
            "countries",
            "languages",
            "budget",
            "gross",
            "poster_url",
            "imdb_url",
            "exported_at",
        ]

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()

                for movie in movies:
                    row = self._flatten_movie(movie)
                    row["exported_at"] = datetime.now().isoformat()
                    writer.writerow(row)

            logger.info(f"Exported {len(movies)} movies to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return None

    def export_json(self, movies: List[Dict], filename: Optional[str] = None) -> Optional[Path]:
        """Export movies to JSON."""
        if not movies:
            logger.warning("No movies to export to JSON")
            return None

        filename = filename or JSON_FILENAME
        filepath = self.export_dir / filename

        try:
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "total_movies": len(movies),
                "movies": [self._flatten_movie(movie) for movie in movies],
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(movies)} movies to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return None

    def _flatten_movie(self, movie: Dict) -> Dict:
        """Flatten nested movie data for export."""
        flat = {}

        for key, value in movie.items():
            if isinstance(value, list):
                flat[key] = "; ".join(str(v) for v in value)
            elif isinstance(value, dict):
                flat[key] = json.dumps(value, ensure_ascii=False)
            else:
                flat[key] = value

        return flat


def create_exporter(export_dir: Path = None) -> DataExporter:
    """Factory function to create an exporter instance."""
    return DataExporter(export_dir) if export_dir else DataExporter()