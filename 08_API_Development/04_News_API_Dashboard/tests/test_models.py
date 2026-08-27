"""
News API Dashboard - Unit Tests for Models
"""

import pytest
from src.models import Article, Source, NewsResponse, parse_article, parse_source, parse_news_response


class TestDataClasses:
    def test_article(self):
        article = Article(
            title="Test Article",
            description="Test description",
            url="https://example.com/article",
            image_url="https://example.com/image.jpg",
            source_name="Test Source",
            author="John Doe",
            published_at="2024-01-15T10:30:00Z",
        )
        assert article.title == "Test Article"
        assert article.source_display == "Test Source"

    def test_article_no_source(self):
        article = Article(title="Test", url="https://example.com")
        assert article.source_display == "Unknown"

    def test_source(self):
        source = Source(
            id="test-source",
            name="Test Source",
            description="A test source",
            url="https://test.com",
            category="technology",
            language="en",
            country="us",
        )
        assert source.display == "Test Source (technology) [US]"

    def test_news_response(self):
        articles = [
            Article(title="Article 1", url="https://example.com/1"),
            Article(title="Article 2", url="https://example.com/2"),
        ]
        response = NewsResponse(
            status="ok",
            total_results=2,
            articles=articles,
        )
        assert response.has_articles is True


class TestParsers:
    def test_parse_article(self):
        data = {
            "title": "Test Article",
            "description": "Test description",
            "content": "Full content",
            "url": "https://example.com/article",
            "urlToImage": "https://example.com/image.jpg",
            "source": {"id": "src1", "name": "Test Source"},
            "author": "John Doe",
            "publishedAt": "2024-01-15T10:30:00Z",
        }
        article = parse_article(data)
        assert article is not None
        assert article.title == "Test Article"
        assert article.source_name == "Test Source"
        assert article.author == "John Doe"

    def test_parse_article_minimal(self):
        data = {"title": "Minimal", "url": "https://example.com"}
        article = parse_article(data)
        assert article is not None
        assert article.title == "Minimal"

    def test_parse_source(self):
        data = {
            "id": "src1",
            "name": "Test Source",
            "description": "A test source",
            "url": "https://test.com",
            "category": "technology",
            "language": "en",
            "country": "us",
        }
        source = parse_source(data)
        assert source is not None
        assert source.id == "src1"
        assert source.name == "Test Source"
        assert source.category == "technology"

    def test_parse_news_response(self):
        data = {
            "status": "ok",
            "totalResults": 2,
            "articles": [
                {"title": "Article 1", "url": "https://example.com/1"},
                {"title": "Article 2", "url": "https://example.com/2"},
            ],
        }
        response = parse_news_response(data)
        assert response is not None
        assert response.status == "ok"
        assert response.total_results == 2
        assert len(response.articles) == 2
        assert response.has_articles is True

    def test_parse_news_response_empty(self):
        data = {
            "status": "ok",
            "totalResults": 0,
            "articles": [],
        }
        response = parse_news_response(data)
        assert response is not None
        assert response.has_articles is False