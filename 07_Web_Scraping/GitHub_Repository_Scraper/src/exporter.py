"""
GitHub Repository Scraper - Exporter Module
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from .config import EXPORTS_DIR, CSV_FILENAME, JSON_FILENAME
from .logger import logger


class DataExporter:
    """Handles exporting repository data to various formats."""

    def __init__(self, export_dir: Path = EXPORTS_DIR):
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_csv(self, repos: List[Dict], filename: Optional[str] = None) -> Optional[Path]:
        """Export repositories to CSV."""
        if not repos:
            logger.warning("No repositories to export to CSV")
            return None

        filename = filename or CSV_FILENAME
        filepath = self.export_dir / filename

        fieldnames = [
            "rank",
            "name",
            "owner",
            "full_name",
            "url",
            "description",
            "language",
            "language_color",
            "stars",
            "forks",
            "today_stars",
            "contributors",
            "topics",
            "license",
            "last_commit",
            "releases",
            "watchers",
            "issues",
            "pull_requests",
            "readme_preview",
            "exported_at",
        ]

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()

                for repo in repos:
                    row = self._flatten_repo(repo)
                    row["exported_at"] = datetime.now().isoformat()
                    writer.writerow(row)

            logger.info(f"Exported {len(repos)} repositories to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return None

    def export_json(self, repos: List[Dict], filename: Optional[str] = None) -> Optional[Path]:
        """Export repositories to JSON."""
        if not repos:
            logger.warning("No repositories to export to JSON")
            return None

        filename = filename or JSON_FILENAME
        filepath = self.export_dir / filename

        try:
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "total_repos": len(repos),
                "repos": [self._flatten_repo(repo) for repo in repos],
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(repos)} repositories to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return None

    def _flatten_repo(self, repo: Dict) -> Dict:
        """Flatten nested repository data for export."""
        flat = {}

        for key, value in repo.items():
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