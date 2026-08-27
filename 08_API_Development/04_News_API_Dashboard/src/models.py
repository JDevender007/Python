"""
News API Dashboard - Data Models
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class Article:
    """News article."""
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    url: str = ""
    image_url: Optional[str] = None
    source_name: str = ""
    source_id: Optional[str] = None
    author: Optional[str] = None
    published_at: str = ""
    category: Optional[str] = None
    country: Optional[str] = None

    @property
    def source_display(self) -> str:
        return self.source_name or self.source_id or "Unknown"

    @property
    def published_date(self) -> str:
        if not self.published_at:
            return "N/A"
        try:
            dt = datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return self.published_at

    @property
    def published_datetime(self) -> str:
        if not self.published_at:
            return "N/A"
        try:
            dt = datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return self.published_at

    @property
    def relative_time(self) -> str:
        if not self.published_at:
            return "N/A"
        try:
            dt = datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))
            now = datetime.now()
            diff = now - dt.replace(tzinfo=None)

            if diff.days > 0:
                return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
            hours = diff.seconds // 3600
            if hours > 0:
                return f"{hours} hour{'s' if hours > 1 else ''} ago"
            minutes = diff.seconds // 60
            if minutes > 0:
                return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
            return "Just now"
        except Exception:
            return self.published_at

    @property
    def reading_time(self) -> str:
        text = (self.title or "") + " " + (self.description or "") + " " + (self.content or "")
        word_count = len(text.split())
        minutes = max(1, round(word_count / 200))
        return f"{minutes} min read"


@dataclass
class Source:
    """News source."""
    id: str
    name: str
    description: Optional[str] = None
    url: str = ""
    category: Optional[str] = None
    language: str = "en"
    country: str = ""

    @property
    def display(self) -> str:
        parts = [self.name]
        if self.category:
            parts.append(f"({self.category})")
        if self.country:
            parts.append(f"[{self.country.upper()}]")
        return " ".join(parts)


@dataclass
class NewsResponse:
    """News API response wrapper."""
    status: str
    total_results: int
    articles: List[Article]
    code: Optional[str] = None
    message: Optional[str] = None

    @property
    def has_articles(self) -> bool:
        return len(self.articles) > 0


@dataclass
class SourcesResponse:
    """Sources API response wrapper."""
    status: str
    sources: List[Source]


def parse_article(data: Dict) -> Optional[Article]:
    """Parse article from API response."""
    try:
        source = data.get("source", {})
        return Article(
            title=data.get("title", ""),
            description=data.get("description"),
            content=data.get("content"),
            url=data.get("url", ""),
            image_url=data.get("urlToImage"),
            source_name=source.get("name", ""),
            source_id=source.get("id"),
            author=data.get("author"),
            published_at=data.get("publishedAt", ""),
        )
    except Exception:
        return None


def parse_source(data: Dict) -> Optional[Source]:
    """Parse source from API response."""
    try:
        return Source(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description"),
            url=data.get("url", ""),
            category=data.get("category"),
            language=data.get("language", "en"),
            country=data.get("country", ""),
        )
    except Exception:
        return None


def parse_news_response(data: Dict) -> Optional[NewsResponse]:
    """Parse news response from API."""
    try:
        articles = []
        for article_data in data.get("articles", []):
            article = parse_article(article_data)
            if article:
                articles.append(article)

        return NewsResponse(
            status=data.get("status", ""),
            total_results=data.get("totalResults", 0),
            articles=articles,
            code=data.get("code"),
            message=data.get("message"),
        )
    except Exception:
        return None


def parse_sources_response(data: Dict) -> Optional[SourcesResponse]:
    """Parse sources response from API."""
    try:
        sources = []
        for source_data in data.get("sources", []):
            source = parse_source(source_data)
            if source:
                sources.append(source)

        return SourcesResponse(
            status=data.get("status", ""),
            sources=sources,
        )
    except Exception:
        return None