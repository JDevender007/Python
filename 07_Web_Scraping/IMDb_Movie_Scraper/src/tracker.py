"""
IMDb Movie Scraper - Tracker Module
Coordinates scraping, parsing, and tracking of movies.
"""

import threading
from typing import List, Dict, Optional, Callable
from .config import DEFAULT_URL, MAX_MOVIES
from .scraper import IMDbScraper, create_scraper
from .parser import MovieParser, create_parser
from .exporter import DataExporter, create_exporter
from .logger import logger


class MovieTracker:
    """Coordinates the movie scraping workflow."""

    def __init__(self):
        self.scraper = create_scraper()
        self.parser = create_parser()
        self.exporter = create_exporter()
        self.movies: List[Dict] = []
        self.detailed_movies: List[Dict] = []
        self.is_scraping = False
        self.progress_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable[[int, int, str], None]) -> None:
        """Set callback for progress updates: callback(current, total, message)."""
        self.progress_callback = callback

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for status updates: callback(message)."""
        self.status_callback = callback

    def _update_progress(self, current: int, total: int, message: str) -> None:
        """Update progress via callback."""
        if self.progress_callback:
            self.progress_callback(current, total, message)

    def _update_status(self, message: str) -> None:
        """Update status via callback."""
        if self.status_callback:
            self.status_callback(message)
        logger.info(message)

    def scrape_chart(self, url: str = DEFAULT_URL, max_movies: int = MAX_MOVIES) -> List[Dict]:
        """Scrape the IMDb Top 250 chart."""
        self.is_scraping = True
        self.movies = []

        try:
            self._update_status("Fetching IMDb Top 250 chart...")
            soup = self.scraper.fetch_top_movies(url)

            if not soup:
                self._update_status("Failed to fetch chart page")
                return []

            self._update_status("Parsing movie list...")
            self.movies = self.parser.parse_top_chart(soup)

            if max_movies and len(self.movies) > max_movies:
                self.movies = self.movies[:max_movies]

            self._update_status(f"Found {len(self.movies)} movies")
            return self.movies

        except Exception as e:
            logger.error(f"Error scraping chart: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_scraping = False

    def scrape_details(self, movie_indices: Optional[List[int]] = None) -> List[Dict]:
        """Scrape detailed information for selected movies."""
        if not self.movies:
            self._update_status("No movies loaded. Scrape chart first.")
            return []

        self.is_scraping = True
        self.detailed_movies = []

        target_movies = self.movies
        if movie_indices:
            target_movies = [self.movies[i] for i in movie_indices if 0 <= i < len(self.movies)]

        total = len(target_movies)

        try:
            for idx, movie in enumerate(target_movies):
                if not self.is_scraping:
                    break

                self._update_progress(idx + 1, total, f"Fetching details for: {movie['title']}")
                self._update_status(f"Scraping details ({idx + 1}/{total}): {movie['title']}")

                details = {}
                if movie.get("url"):
                    detail_soup = self.scraper.fetch_movie_details(movie["url"])
                    if detail_soup:
                        details = self.parser.parse_movie_details(detail_soup)

                detailed_movie = {**movie, **details}
                self.detailed_movies.append(detailed_movie)

            self._update_status(f"Completed scraping details for {len(self.detailed_movies)} movies")
            return self.detailed_movies

        except Exception as e:
            logger.error(f"Error scraping details: {e}")
            self._update_status(f"Error: {e}")
            return []
        finally:
            self.is_scraping = False

    def stop(self) -> None:
        """Stop the scraping process."""
        self.is_scraping = False
        self._update_status("Scraping stopped by user")

    def get_movies(self) -> List[Dict]:
        """Get basic movie list."""
        return self.movies

    def get_detailed_movies(self) -> List[Dict]:
        """Get detailed movie list."""
        return self.detailed_movies if self.detailed_movies else self.movies

    def export_csv(self, filename: Optional[str] = None) -> Optional[str]:
        """Export movies to CSV."""
        movies = self.get_detailed_movies()
        if not movies:
            self._update_status("No data to export")
            return None

        path = self.exporter.export_csv(movies, filename)
        if path:
            self._update_status(f"Exported to CSV: {path.name}")
        return str(path) if path else None

    def export_json(self, filename: Optional[str] = None) -> Optional[str]:
        """Export movies to JSON."""
        movies = self.get_detailed_movies()
        if not movies:
            self._update_status("No data to export")
            return None

        path = self.exporter.export_json(movies, filename)
        if path:
            self._update_status(f"Exported to JSON: {path.name}")
        return str(path) if path else None

    def clear(self) -> None:
        """Clear all movie data."""
        self.movies = []
        self.detailed_movies = []
        self._update_status("Data cleared")


def create_tracker() -> MovieTracker:
    """Factory function to create a tracker instance."""
    return MovieTracker()