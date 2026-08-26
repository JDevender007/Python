"""
GitHub Repository Scraper - Unit Tests for Parser
"""

import pytest
from bs4 import BeautifulSoup
from src.parser import RepoParser, create_parser


class TestRepoParser:
    @pytest.fixture
    def parser(self):
        return create_parser()

    @pytest.fixture
    def sample_trending_html(self):
        return """
        <html>
            <body>
                <article class="Box-row">
                    <h2 class="h3">
                        <a href="/owner/repo1">owner / repo1</a>
                    </h2>
                    <p class="col-9">A great repository</p>
                    <span itemprop="programmingLanguage">Python</span>
                    <span class="repo-language-color" style="background-color: #3572A5"></span>
                    <a href="/owner/repo1/stargazers">1.5k</a>
                    <a href="/owner/repo1/forks">300</a>
                    <span class="float-sm-right">50 stars today</span>
                    <div class="avatar-stack">
                        <img alt="@user1">
                        <img alt="@user2">
                    </div>
                </article>
                <article class="Box-row">
                    <h1><a href="/owner2/repo2">owner2 / repo2</a></h1>
                    <p class="col-9">Another repo</p>
                    <span itemprop="programmingLanguage">JavaScript</span>
                    <a href="/owner2/repo2/stargazers">2.1k</a>
                    <a href="/owner2/repo2/forks">500</a>
                </article>
            </body>
        </html>
        """

    def test_parse_trending(self, parser, sample_trending_html):
        soup = BeautifulSoup(sample_trending_html, "html.parser")
        repos = parser.parse_trending(soup)

        assert len(repos) == 2

        assert repos[0]["rank"] == 1
        assert repos[0]["name"] == "repo1"
        assert repos[0]["owner"] == "owner"
        assert repos[0]["full_name"] == "owner / repo1"
        assert repos[0]["url"] == "/owner/repo1"
        assert repos[0]["description"] == "A great repository"
        assert repos[0]["language"] == "Python"
        assert repos[0]["language_color"] == "#3572A5"
        assert repos[0]["stars"] == 1500
        assert repos[0]["forks"] == 300
        assert repos[0]["today_stars"] == 50
        assert repos[0]["contributors"] == ["user1", "user2"]

        assert repos[1]["rank"] == 2
        assert repos[1]["name"] == "repo2"
        assert repos[1]["owner"] == "owner2"
        assert repos[1]["language"] == "JavaScript"
        assert repos[1]["stars"] == 2100
        assert repos[1]["forks"] == 500

    def test_parse_trending_empty(self, parser):
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        repos = parser.parse_trending(soup)
        assert repos == []


class TestUserReposParser:
    @pytest.fixture
    def parser(self):
        return create_parser()

    @pytest.fixture
    def sample_user_repos_html(self):
        return """
        <html>
            <body>
                <ul id="user-repositories-list">
                    <li>
                        <h3><a href="/user/repo1">repo1</a></h3>
                        <p itemprop="description">First repo</p>
                        <span itemprop="programmingLanguage">Python</span>
                        <a href="/user/repo1/stargazers">100</a>
                        <a href="/user/repo1/forks">20</a>
                        <relative-time datetime="2024-01-15">Jan 15, 2024</relative-time>
                    </li>
                    <li>
                        <h3><a href="/user/repo2">repo2</a></h3>
                        <p itemprop="description">Second repo</p>
                        <span itemprop="programmingLanguage">Go</span>
                        <a href="/user/repo2/stargazers">50</a>
                        <a href="/user/repo2/forks">10</a>
                    </li>
                </ul>
            </body>
        </html>
        """

    def test_parse_user_repos(self, parser, sample_user_repos_html):
        soup = BeautifulSoup(sample_user_repos_html, "html.parser")
        repos = parser.parse_user_repos(soup)

        assert len(repos) == 2

        assert repos[0]["rank"] == 1
        assert repos[0]["name"] == "repo1"
        assert repos[0]["full_name"] == "repo1"
        assert repos[0]["url"] == "/user/repo1"
        assert repos[0]["description"] == "First repo"
        assert repos[0]["language"] == "Python"
        assert repos[0]["stars"] == 100
        assert repos[0]["forks"] == 20
        assert repos[0]["updated"] == "Jan 15, 2024"

        assert repos[1]["rank"] == 2
        assert repos[1]["name"] == "repo2"
        assert repos[1]["language"] == "Go"
        assert repos[1]["stars"] == 50


class TestRepoDetailsParser:
    @pytest.fixture
    def parser(self):
        return create_parser()

    @pytest.fixture
    def sample_repo_detail_html(self):
        return """
        <html>
            <body>
                <p class="f4 my-3">This is the about section</p>
                <a class="topic-tag" href="/topics/python">python</a>
                <a class="topic-tag" href="/topics/cli">cli</a>
                <a href="/user/repo/license">MIT</a>
                <relative-time datetime="2024-01-15T10:00:00Z">Jan 15, 2024</relative-time>
                <a href="/user/repo/releases">v1.0.0</a>
                <a href="/user/repo/watchers">10</a>
                <a href="/user/repo/issues">5 Issues</a>
                <a href="/user/repo/pulls">3 Pull requests</a>
                <article class="markdown-body"># README\nThis is the readme content</article>
            </body>
        </html>
        """

    def test_parse_topics(self, parser, sample_repo_detail_html):
        soup = BeautifulSoup(sample_repo_detail_html, "html.parser")
        details = parser.parse_repo_details(soup)
        assert "python" in details["topics"]
        assert "cli" in details["topics"]

    def test_parse_license(self, parser, sample_repo_detail_html):
        soup = BeautifulSoup(sample_repo_detail_html, "html.parser")
        details = parser.parse_repo_details(soup)
        assert details["license"] == "MIT"

    def test_parse_last_commit(self, parser, sample_repo_detail_html):
        soup = BeautifulSoup(sample_repo_detail_html, "html.parser")
        details = parser.parse_repo_details(soup)
        assert details["last_commit"] == "2024-01-15T10:00:00Z"

    def test_parse_releases(self, parser, sample_repo_detail_html):
        soup = BeautifulSoup(sample_repo_detail_html, "html.parser")
        details = parser.parse_repo_details(soup)
        assert details["releases"] == "v1.0.0"

    def test_parse_watchers(self, parser, sample_repo_detail_html):
        soup = BeautifulSoup(sample_repo_detail_html, "html.parser")
        details = parser.parse_repo_details(soup)
        assert details["watchers"] == 10

    def test_parse_issues(self, parser, sample_repo_detail_html):
        soup = BeautifulSoup(sample_repo_detail_html, "html.parser")
        details = parser.parse_repo_details(soup)
        assert details["issues"] == 5

    def test_parse_pull_requests(self, parser, sample_repo_detail_html):
        soup = BeautifulSoup(sample_repo_detail_html, "html.parser")
        details = parser.parse_repo_details(soup)
        assert details["pull_requests"] == 3

    def test_parse_readme(self, parser, sample_repo_detail_html):
        soup = BeautifulSoup(sample_repo_detail_html, "html.parser")
        details = parser.parse_repo_details(soup)
        assert "readme content" in details["readme"]