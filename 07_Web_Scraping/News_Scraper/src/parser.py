from __future__ import annotations

from bs4 import BeautifulSoup

from src.utils import (
    build_absolute_url,
    clean_text,
)


class NewsParser:

    def parse(
        self,
        html,
        base_url,
        limit=100,
    ):

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        articles = []

        for element in soup.find_all("article"):

            article = self.parse_article(
                element,
                base_url,
            )

            if article:

                articles.append(article)

            if len(articles) >= limit:

                break

        if not articles:

            articles = self.parse_headings(
                soup,
                base_url,
                limit,
            )

        return articles

    def parse_article(
        self,
        element,
        base_url,
    ):

        title_element = element.find(["h1", "h2", "h3"])

        if not title_element:

            return None

        title = clean_text(title_element.get_text())

        link_element = title_element.find("a")

        if not link_element:

            link_element = element.find(
                "a",
                href=True,
            )

        link = ""

        if link_element:

            link = build_absolute_url(
                base_url,
                link_element.get("href"),
            )

        summary_element = element.find(["p"])

        summary = ""

        if summary_element:

            summary = clean_text(summary_element.get_text())

        time_element = element.find("time")

        date = ""

        if time_element:

            date = clean_text(
                time_element.get(
                    "datetime",
                    time_element.get_text(),
                )
            )

        return {
            "title": title,
            "link": link,
            "date": date,
            "summary": summary,
        }

    def parse_headings(
        self,
        soup,
        base_url,
        limit,
    ):

        articles = []

        for heading in soup.find_all(["h1", "h2", "h3"]):

            title = clean_text(heading.get_text())

            if not title:

                continue

            link_element = heading.find(
                "a",
                href=True,
            )

            if not link_element:

                parent = heading.parent

                if parent:

                    link_element = parent.find(
                        "a",
                        href=True,
                    )

            link = ""

            if link_element:

                link = build_absolute_url(
                    base_url,
                    link_element.get("href"),
                )

            articles.append(
                {
                    "title": title,
                    "link": link,
                    "date": "",
                    "summary": "",
                }
            )

            if len(articles) >= limit:

                break

        return articles
