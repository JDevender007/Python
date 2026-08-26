"""
GitHub Repository Scraper - Parser Module
"""

from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from .config import MAX_REPOS
from .logger import logger
from .utils import (
    clean_text,
    extract_number,
    parse_relative_time,
    safe_get_text,
    safe_get_attr,
    parse_language_color,
)


class RepoParser:
    """Parses repository data from GitHub HTML."""

    def parse_trending(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse GitHub trending page."""
        repos = []

        try:
            articles = soup.select("article.Box-row")
            logger.info(f"Found {len(articles)} repositories on trending page")

            for idx, article in enumerate(articles[:MAX_REPOS], 1):
                try:
                    repo = self._parse_trending_repo(article, idx)
                    if repo:
                        repos.append(repo)
                except Exception as e:
                    logger.warning(f"Error parsing repo {idx}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing trending page: {e}")

        logger.info(f"Successfully parsed {len(repos)} repositories")
        return repos

    def _parse_trending_repo(self, article, rank: int) -> Optional[Dict]:
        """Parse a single repository from trending page."""
        # Repository name and link
        h2 = article.select_one("h2.h3 a") or article.select_one("h1 a")
        if not h2:
            return None

        full_name = clean_text(h2.get_text())
        repo_url = h2.get("href", "")

        # Split owner/repo
        parts = full_name.split("/")
        owner = parts[0].strip() if len(parts) > 1 else ""
        name = parts[1].strip() if len(parts) > 1 else full_name

        # Description
        desc_elem = article.select_one("p.col-9")
        description = clean_text(desc_elem.get_text()) if desc_elem else ""

        # Language
        lang_elem = article.select_one('span[itemprop="programmingLanguage"]')
        language = clean_text(lang_elem.get_text()) if lang_elem else None

        lang_color = ""
        lang_color_elem = article.select_one('span.repo-language-color')
        if lang_color_elem and lang_color_elem.has_attr("style"):
            lang_color = parse_language_color(lang_color_elem["style"])

        # Stars and forks
        stars = None
        forks = None
        stars_elem = article.select_one('a[href*="/stargazers"]')
        if stars_elem:
            stars = extract_number(stars_elem.get_text())
        forks_elem = article.select_one('a[href*="/forks"]')
        if forks_elem:
            forks = extract_number(forks_elem.get_text())

        # Today's stars
        today_stars = None
        today_elem = article.select_one("span.float-sm-right") or article.select_one('span[class*="float"]')
        if today_elem:
            today_stars = extract_number(today_elem.get_text())

        # Built by (contributors)
        contributors = []
        avatar_stack = article.select(".avatar-stack img")
        for img in avatar_stack[:5]:
            alt = img.get("alt", "")
            if alt and alt != "@":
                contributors.append(alt.replace("@", ""))

        return {
            "rank": rank,
            "name": name,
            "owner": owner,
            "full_name": full_name,
            "url": repo_url,
            "description": description,
            "language": language,
            "language_color": lang_color,
            "stars": stars,
            "forks": forks,
            "today_stars": today_stars,
            "contributors": contributors,
        }

    def parse_user_repos(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse user repositories page."""
        repos = []

        try:
            repo_items = soup.select("#user-repositories-list li")
            logger.info(f"Found {len(repo_items)} repositories for user")

            for idx, item in enumerate(repo_items[:MAX_REPOS], 1):
                try:
                    repo = self._parse_user_repo(item, idx)
                    if repo:
                        repos.append(repo)
                except Exception as e:
                    logger.warning(f"Error parsing user repo {idx}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing user repos: {e}")

        return repos

    def _parse_user_repo(self, item, rank: int) -> Optional[Dict]:
        """Parse a single user repository."""
        name_link = item.select_one("h3 a")
        if not name_link:
            return None

        name = clean_text(name_link.get_text())
        repo_url = name_link.get("href", "")

        desc_elem = item.select_one("p[itemprop='description']")
        description = clean_text(desc_elem.get_text()) if desc_elem else ""

        language_elem = item.select_one('span[itemprop="programmingLanguage"]')
        language = clean_text(language_elem.get_text()) if language_elem else None

        stars_elem = item.select_one('a[href*="/stargazers"]')
        stars = extract_number(stars_elem.get_text()) if stars_elem else None

        forks_elem = item.select_one('a[href*="/forks"]')
        forks = extract_number(forks_elem.get_text()) if forks_elem else None

        updated_elem = item.select_one("relative-time")
        updated = parse_relative_time(updated_elem.get_text()) if updated_elem else None
        if updated:
            updated = updated[0].upper() + updated[1:] if len(updated) > 0 else updated

        return {
            "rank": rank,
            "name": name,
            "owner": "",
            "full_name": name,
            "url": repo_url,
            "description": description,
            "language": language,
            "stars": stars,
            "forks": forks,
            "updated": updated,
        }

    def parse_repo_details(self, soup: BeautifulSoup) -> Dict:
        """Parse detailed repository information."""
        details = {}

        try:
            # About/Description
            about_elem = soup.select_one('p.f4.my-3') or soup.select_one('div.repository-content p')
            if about_elem:
                details["about"] = clean_text(about_elem.get_text())

            # Topics/Tags
            details["topics"] = self._parse_topics(soup)

            # License
            details["license"] = self._parse_license(soup)

            # Last commit
            details["last_commit"] = self._parse_last_commit(soup)

            # Releases
            details["releases"] = self._parse_releases(soup)

            # Stats
            details["watchers"] = self._parse_watchers(soup)
            details["issues"] = self._parse_issues(soup)
            details["pull_requests"] = self._parse_pull_requests(soup)

            # README preview
            details["readme"] = self._parse_readme(soup)

        except Exception as e:
            logger.error(f"Error parsing repo details: {e}")

        return details

    def _parse_topics(self, soup: BeautifulSoup) -> List[str]:
        """Parse repository topics/tags."""
        topics = []
        try:
            topic_elements = soup.select('a.topic-tag')
            for elem in topic_elements:
                topic = clean_text(elem.get_text())
                if topic and topic not in topics:
                    topics.append(topic)
        except Exception:
            pass
        return topics

    def _parse_license(self, soup: BeautifulSoup) -> Optional[str]:
        """Parse repository license."""
        try:
            license_elem = soup.select_one('a[href*="/license"]') or soup.select_one('span[itemprop="license"]')
            if license_elem:
                return clean_text(license_elem.get_text())
        except Exception:
            pass
        return None

    def _parse_last_commit(self, soup: BeautifulSoup) -> Optional[str]:
        """Parse last commit info."""
        try:
            commit_elem = soup.select_one('relative-time')
            if commit_elem:
                return commit_elem.get("datetime", "")
        except Exception:
            pass
        return None

    def _parse_releases(self, soup: BeautifulSoup) -> Optional[str]:
        """Parse releases count."""
        try:
            releases_elem = soup.select_one('a[href*="/releases"]')
            if releases_elem:
                return clean_text(releases_elem.get_text())
        except Exception:
            pass
        return None

    def _parse_watchers(self, soup: BeautifulSoup) -> Optional[int]:
        """Parse watchers count."""
        try:
            watchers_elem = soup.select_one('a[href*="/watchers"]')
            if watchers_elem:
                return extract_number(watchers_elem.get_text())
        except Exception:
            pass
        return None

    def _parse_issues(self, soup: BeautifulSoup) -> Optional[int]:
        """Parse open issues count."""
        try:
            issues_elem = soup.select_one('a[href*="/issues"]')
            if issues_elem:
                text = clean_text(issues_elem.get_text())
                # Extract number from "X Issues" or similar
                import re
                match = re.search(r"(\d+)", text)
                if match:
                    return int(match.group(1))
        except Exception:
            pass
        return None

    def _parse_pull_requests(self, soup: BeautifulSoup) -> Optional[int]:
        """Parse pull requests count."""
        try:
            pr_elem = soup.select_one('a[href*="/pulls"]')
            if pr_elem:
                text = clean_text(pr_elem.get_text())
                import re
                match = re.search(r"(\d+)", text)
                if match:
                    return int(match.group(1))
        except Exception:
            pass
        return None

    def _parse_readme(self, soup: BeautifulSoup) -> Optional[str]:
        """Parse README content preview."""
        try:
            readme_elem = soup.select_one('article.markdown-body') or soup.select_one('#readme')
            if readme_elem:
                return clean_text(readme_elem.get_text())[:500]
        except Exception:
            pass
        return None


def create_parser() -> RepoParser:
    """Factory function to create a parser instance."""
    return RepoParser()