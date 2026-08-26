"""
IMDb Movie Scraper - Unit Tests for Parser
"""

import pytest
from bs4 import BeautifulSoup
from src.parser import MovieParser, create_parser


class TestMovieParser:
    @pytest.fixture
    def parser(self):
        return create_parser()

    @pytest.fixture
    def sample_chart_html(self):
        return """
        <html>
            <body>
                <table>
                    <tbody class="lister-list">
                        <tr>
                            <td class="titleColumn">
                                <a href="/title/tt0111161/">The Shawshank Redemption</a>
                                <span class="secondaryInfo">(1994)</span>
                            </td>
                            <td class="ratingColumn imdbRating">
                                <strong title="2,500,000 votes">9.3</strong>
                            </td>
                        </tr>
                        <tr>
                            <td class="titleColumn">
                                <a href="/title/tt0068646/">The Godfather</a>
                                <span class="secondaryInfo">(1972)</span>
                            </td>
                            <td class="ratingColumn imdbRating">
                                <strong title="1,800,000 votes">9.2</strong>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </body>
        </html>
        """

    def test_parse_top_chart(self, parser, sample_chart_html):
        soup = BeautifulSoup(sample_chart_html, "html.parser")
        movies = parser.parse_top_chart(soup)

        assert len(movies) == 2

        assert movies[0]["rank"] == 1
        assert movies[0]["title"] == "The Shawshank Redemption"
        assert movies[0]["year"] == 1994
        assert movies[0]["rating"] == 9.3
        assert movies[0]["votes"] == 2_500_000
        assert movies[0]["url"] == "/title/tt0111161/"

        assert movies[1]["rank"] == 2
        assert movies[1]["title"] == "The Godfather"
        assert movies[1]["year"] == 1972
        assert movies[1]["rating"] == 9.2
        assert movies[1]["votes"] == 1_800_000

    def test_parse_top_chart_empty(self, parser):
        html = "<html><body><table><tbody class='lister-list'></tbody></table></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        movies = parser.parse_top_chart(soup)
        assert movies == []

    def test_parse_top_chart_missing_elements(self, parser):
        html = """
        <html><body>
            <table><tbody class="lister-list">
                <tr><td class="titleColumn"></td></tr>
            </tbody></table>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        movies = parser.parse_top_chart(soup)
        assert movies == []


class TestMovieDetailsParser:
    @pytest.fixture
    def parser(self):
        return create_parser()

    @pytest.fixture
    def sample_movie_html(self):
        return """
        <html>
            <body>
                <a href="/genre/drama">Drama</a>
                <a href="/genre/crime">Crime</a>
                <li data-testid="title-techspec_runtime">2h 30m</li>
                <li data-testid="title-pc-principal-credit">
                    <a href="/name/nm0000000/">Frank Darabont</a>
                </li>
                <span data-testid="plot-xl">Two imprisoned men bond over a number of years.</span>
                <a href="/parentalguide">R</a>
                <li data-testid="title-details-releasedate">
                    <a href="/releaseinfo">September 23, 1994</a>
                </li>
                <li data-testid="title-details-origin">
                    <a href="/country/us">United States</a>
                </li>
                <li data-testid="title-details-languages">
                    <a href="/language/en">English</a>
                </li>
                <li data-testid="title-boxoffice-budget">Budget: $25,000,000</li>
                <li data-testid="title-boxoffice-cumulativeworldwidegross">Gross worldwide: $58,300,000</li>
                <img data-testid="hero-media__poster" src="https://example.com/poster.jpg">
            </body>
        </html>
        """

    def test_parse_genres(self, parser, sample_movie_html):
        soup = BeautifulSoup(sample_movie_html, "html.parser")
        details = parser.parse_movie_details(soup)
        assert "Drama" in details["genres"]
        assert "Crime" in details["genres"]

    def test_parse_duration(self, parser, sample_movie_html):
        soup = BeautifulSoup(sample_movie_html, "html.parser")
        details = parser.parse_movie_details(soup)
        assert details["duration_minutes"] == 150

    def test_parse_director(self, parser, sample_movie_html):
        soup = BeautifulSoup(sample_movie_html, "html.parser")
        details = parser.parse_movie_details(soup)
        assert details["director"] == "Frank Darabont"

    def test_parse_description(self, parser, sample_movie_html):
        soup = BeautifulSoup(sample_movie_html, "html.parser")
        details = parser.parse_movie_details(soup)
        assert "imprisoned men bond" in details["description"]

    def test_parse_certificate(self, parser, sample_movie_html):
        soup = BeautifulSoup(sample_movie_html, "html.parser")
        details = parser.parse_movie_details(soup)
        assert details["certificate"] == "R"

    def test_parse_release_date(self, parser, sample_movie_html):
        soup = BeautifulSoup(sample_movie_html, "html.parser")
        details = parser.parse_movie_details(soup)
        assert details["release_date"] == "September 23, 1994"

    def test_parse_countries(self, parser, sample_movie_html):
        soup = BeautifulSoup(sample_movie_html, "html.parser")
        details = parser.parse_movie_details(soup)
        assert "United States" in details["countries"]

    def test_parse_languages(self, parser, sample_movie_html):
        soup = BeautifulSoup(sample_movie_html, "html.parser")
        details = parser.parse_movie_details(soup)
        assert "English" in details["languages"]

    def test_parse_budget(self, parser, sample_movie_html):
        soup = BeautifulSoup(sample_movie_html, "html.parser")
        details = parser.parse_movie_details(soup)
        assert "$25,000,000" in details["budget"]

    def test_parse_gross(self, parser, sample_movie_html):
        soup = BeautifulSoup(sample_movie_html, "html.parser")
        details = parser.parse_movie_details(soup)
        assert "$58,300,000" in details["gross"]

    def test_parse_poster(self, parser, sample_movie_html):
        soup = BeautifulSoup(sample_movie_html, "html.parser")
        details = parser.parse_movie_details(soup)
        assert details["poster_url"] == "https://example.com/poster.jpg"