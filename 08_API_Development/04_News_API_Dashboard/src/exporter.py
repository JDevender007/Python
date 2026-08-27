"""
News API Dashboard - Exporter Module
Handles exporting articles, sources, and search results to CSV and JSON.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from .config import EXPORTS_DIR
from .logger import logger


class NewsExporter:
    """Handles exporting news data."""

    def __init__(self, export_dir: Path = EXPORTS_DIR):
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_articles(self, articles: List, filename: str = None) -> Optional[Path]:
        """Export articles to CSV."""
        if not articles:
            logger.warning("No articles to export")
            return None

        filename = filename or f"news_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Title", "Description", "Content", "URL", "Image URL",
                    "Source", "Author", "Published At", "Category", "Country",
                    "Reading Time"
                ])

                for article in articles:
                    writer.writerow([
                        article.title,
                        article.description or "",
                        (article.content or "")[:500],
                        article.url,
                        article.image_url or "",
                        article.source_display,
                        article.author or "",
                        article.published_datetime,
                        article.category or "",
                        article.country or "",
                        article.reading_time,
                    ])

            logger.info(f"Exported {len(articles)} articles to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting articles to CSV: {e}")
            return None

    def export_sources(self, sources: List, filename: str = None) -> Optional[Path]:
        """Export sources to CSV."""
        if not sources:
            logger.warning("No sources to export")
            return None

        filename = filename or f"news_sources_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ID", "Name", "Description", "URL", "Category", "Language", "Country"
                ])

                for source in sources:
                    writer.writerow([
                        source.id,
                        source.name,
                        source.description or "",
                        source.url,
                        source.category or "",
                        source.language,
                        source.country,
                    ])

            logger.info(f"Exported {len(sources)} sources to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting sources to CSV: {e}")
            return None

    def export_articles_json(self, articles: List, filename: str = None) -> Optional[Path]:
        """Export articles to JSON."""
        if not articles:
            logger.warning("No articles to export")
            return None

        filename = filename or f"news_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.export_dir / filename

        try:
            articles_data = []
            for article in articles:
                articles_data.append({
                    "title": article.title,
                    "description": article.description,
                    "content": article.content,
                    "url": article.url,
                    "image_url": article.image_url,
                    "source_name": article.source_name,
                    "source_id": article.source_id,
                    "author": article.author,
                    "published_at": article.published_at,
                    "category": article.category,
                    "country": article.country,
                    "reading_time": article.reading_time,
                    "relative_time": article.relative_time,
                })

            data = {
                "exported_at": datetime.now().isoformat(),
                "total_articles": len(articles),
                "articles": articles_data
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(articles)} articles to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting articles to JSON: {e}")
            return None

    def export_sources_json(self, sources: List, filename: str = None) -> Optional[Path]:
        """Export sources to JSON."""
        if not sources:
            logger.warning("No sources to export")
            return None

        filename = filename or f"news_sources_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.export_dir / filename

        try:
            sources_data = []
            for source in sources:
                sources_data.append({
                    "id": source.id,
                    "name": source.name,
                    "description": source.description,
                    "url": source.url,
                    "category": source.category,
                    "language": source.language,
                    "country": source.country,
                })

            data = {
                "exported_at": datetime.now().isoformat(),
                "total_sources": len(sources),
                "sources": sources_data
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(sources)} sources to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting sources to JSON: {e}")
            return None


def create_exporter(export_dir: Path = None) -> NewsExporter:
    """Factory function to create exporter."""
    return NewsExporter(export_dir) if export_dir else NewsExporter()