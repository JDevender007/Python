"""
IMDb Movie Scraper - Parser Module
"""

from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from .config import MAX_MOVIES
from .logger import logger
from .utils import (
    clean_text,
    extract_year,
    extract_rating,
    extract_votes,
    parse_duration,
    safe_get_text,
    safe_get_attr,
)


class MovieParser:
    """Parses movie data from IMDb HTML."""

    def parse_top_chart(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse the IMDb Top 250 chart page."""
        movies = []

        try:
            rows = soup.select("tbody.lister-list tr")
            logger.info(f"Found {len(rows)} movie rows in chart")

            for idx, row in enumerate(rows[:MAX_MOVIES], 1):
                try:
                    movie = self._parse_chart_row(row, idx)
                    if movie:
                        movies.append(movie)
                except Exception as e:
                    logger.warning(f"Error parsing row {idx}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing top chart: {e}")

        logger.info(f"Successfully parsed {len(movies)} movies from chart")
        return movies

    def _parse_chart_row(self, row, rank: int) -> Optional[Dict]:
        """Parse a single row from the top chart."""
        title_column = row.select_one("td.titleColumn")
        rating_column = row.select_one("td.ratingColumn.imdbRating")

        if not title_column:
            return None

        title_link = title_column.select_one("a")
        if not title_link:
            return None

        title = clean_text(title_link.get_text())
        movie_url = title_link.get("href", "")

        year_span = title_column.select_one("span.secondaryInfo")
        year = extract_year(year_span.get_text()) if year_span else None

        rating = None
        votes = None
        if rating_column:
            rating_strong = rating_column.select_one("strong")
            if rating_strong:
                rating = extract_rating(rating_strong.get_text())
                votes_text = rating_strong.get("title", "")
                votes = extract_votes(votes_text)

        return {
            "rank": rank,
            "title": title,
            "year": year,
            "rating": rating,
            "votes": votes,
            "url": movie_url,
        }

    def parse_movie_details(self, soup: BeautifulSoup) -> Dict:
        """Parse detailed movie information from movie page."""
        details = {}

        try:
            details["genres"] = self._parse_genres(soup)
            details["duration_minutes"] = self._parse_duration(soup)
            details["director"] = self._parse_director(soup)
            details["writers"] = self._parse_writers(soup)
            details["stars"] = self._parse_stars(soup)
            details["description"] = self._parse_description(soup)
            details["certificate"] = self._parse_certificate(soup)
            details["release_date"] = self._parse_release_date(soup)
            details["countries"] = self._parse_countries(soup)
            details["languages"] = self._parse_languages(soup)
            details["budget"] = self._parse_budget(soup)
            details["gross"] = self._parse_gross(soup)
            details["poster_url"] = self._parse_poster(soup)

        except Exception as e:
            logger.error(f"Error parsing movie details: {e}")

        return details

    def _parse_genres(self, soup: BeautifulSoup) -> List[str]:
        """Parse movie genres."""
        genres = []
        try:
            genre_elements = soup.select('a[href*="/genre/"]')
            for elem in genre_elements:
                genre = clean_text(elem.get_text())
                if genre and genre not in genres:
                    genres.append(genre)
        except Exception:
            pass
        return genres

    def _parse_duration(self, soup: BeautifulSoup) -> Optional[int]:
        """Parse movie duration in minutes."""
        try:
            duration_elem = soup.select_one('li[data-testid="title-techspec_runtime"]')
            if duration_elem:
                return parse_duration(duration_elem.get_text())
        except Exception:
            pass
        return None

    def _parse_director(self, soup: BeautifulSoup) -> Optional[str]:
        """Parse director name."""
        try:
            director_elem = soup.select_one('li[data-testid="title-pc-principal-credit"] a[href*="/name/"]')
            if director_elem:
                return clean_text(director_elem.get_text())
        except Exception:
            pass
        return None

    def _parse_writers(self, soup: BeautifulSoup) -> List[str]:
        """Parse writers."""
        writers = []
        try:
            writer_section = soup.select('li[data-testid="title-pc-principal-credit"]')
            for section in writer_section:
                if "Writer" in section.get_text() or "Screenplay" in section.get_text():
                    writer_links = section.select('a[href*="/name/"]')
                    for link in writer_links:
                        writer = clean_text(link.get_text())
                        if writer and writer not in writers:
                            writers.append(writer)
        except Exception:
            pass
        return writers

    def _parse_stars(self, soup: BeautifulSoup) -> List[str]:
        """Parse starring actors."""
        stars = []
        try:
            star_elements = soup.select('a[data-testid="title-cast-item__actor"]')
            for elem in star_elements[:10]:
                star = clean_text(elem.get_text())
                if star and star not in stars:
                    stars.append(star)
        except Exception:
            pass
        return stars

    def _parse_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Parse movie description/plot."""
        try:
            desc_elem = soup.select_one('span[data-testid="plot-xl"]')
            if not desc_elem:
                desc_elem = soup.select_one('span[data-testid="plot-l"]')
            if desc_elem:
                return clean_text(desc_elem.get_text())
        except Exception:
            pass
        return None

    def _parse_certificate(self, soup: BeautifulSoup) -> Optional[str]:
        """Parse age certificate."""
        try:
            cert_elem = soup.select_one('a[href*="/parentalguide"]')
            if cert_elem:
                return clean_text(cert_elem.get_text())
        except Exception:
            pass
        return None

    def _parse_release_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Parse release date."""
        try:
            date_elem = soup.select_one('li[data-testid="title-details-releasedate"] a')
            if date_elem:
                return clean_text(date_elem.get_text())
        except Exception:
            pass
        return None

    def _parse_countries(self, soup: BeautifulSoup) -> List[str]:
        """Parse production countries."""
        countries = []
        try:
            country_elements = soup.select('li[data-testid="title-details-origin"] a[href*="/country/"]')
            for elem in country_elements:
                country = clean_text(elem.get_text())
                if country and country not in countries:
                    countries.append(country)
        except Exception:
            pass
        return countries

    def _parse_languages(self, soup: BeautifulSoup) -> List[str]:
        """Parse languages."""
        languages = []
        try:
            lang_elements = soup.select('li[data-testid="title-details-languages"] a[href*="/language/"]')
            for elem in lang_elements:
                lang = clean_text(elem.get_text())
                if lang and lang not in languages:
                    languages.append(lang)
        except Exception:
            pass
        return languages

    def _parse_budget(self, soup: BeautifulSoup) -> Optional[str]:
        """Parse budget."""
        try:
            budget_elem = soup.select_one('li[data-testid="title-boxoffice-budget"]')
            if budget_elem:
                return clean_text(budget_elem.get_text().replace("Budget", ""))
        except Exception:
            pass
        return None

    def _parse_gross(self, soup: BeautifulSoup) -> Optional[str]:
        """Parse gross revenue."""
        try:
            gross_elem = soup.select_one('li[data-testid="title-boxoffice-cumulativeworldwidegross"]')
            if gross_elem:
                return clean_text(gross_elem.get_text().replace("Gross worldwide", ""))
        except Exception:
            pass
        return None

    def _parse_poster(self, soup: BeautifulSoup) -> Optional[str]:
        """Parse poster image URL."""
        try:
            poster_elem = soup.select_one('img[data-testid="hero-media__poster"]')
            if not poster_elem:
                poster_elem = soup.select_one('div.ipc-poster img')
            if poster_elem and poster_elem.has_attr("src"):
                return poster_elem["src"]
        except Exception:
            pass
        return None


def create_parser() -> MovieParser:
    """Factory function to create a parser instance."""
    return MovieParser()