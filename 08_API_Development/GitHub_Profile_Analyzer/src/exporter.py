"""
GitHub Profile Analyzer - Exporter Module
Handles exporting profile, repos, stats, and events to CSV and JSON.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from .config import EXPORTS_DIR
from .logger import logger


class GitHubExporter:
    """Handles exporting GitHub data."""

    def __init__(self, export_dir: Path = EXPORTS_DIR):
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_user_profile(self, user, filename: str = None) -> Optional[Path]:
        """Export user profile to CSV."""
        if not user:
            logger.warning("No user data to export")
            return None

        filename = filename or f"github_profile_{user.login}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Field", "Value"])
                writer.writerow(["Username", user.login])
                writer.writerow(["Name", user.name or ""])
                writer.writerow(["ID", user.id])
                writer.writerow(["Bio", user.bio or ""])
                writer.writerow(["Company", user.company or ""])
                writer.writerow(["Blog", user.blog or ""])
                writer.writerow(["Location", user.location or ""])
                writer.writerow(["Email", user.email or ""])
                writer.writerow(["Twitter", user.twitter_username or ""])
                writer.writerow(["Public Repos", user.public_repos])
                writer.writerow(["Public Gists", user.public_gists])
                writer.writerow(["Followers", user.followers])
                writer.writerow(["Following", user.following])
                writer.writerow(["Created At", user.created_at])
                writer.writerow(["Updated At", user.updated_at])
                writer.writerow(["Profile URL", user.html_url])
                writer.writerow(["Account Age (days)", user.account_age_days])
                writer.writerow(["Exported At", datetime.now().isoformat()])

            logger.info(f"Exported user profile to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting user profile to CSV: {e}")
            return None

    def export_repositories(self, repos: List, filename: str = None) -> Optional[Path]:
        """Export repositories to CSV."""
        if not repos:
            logger.warning("No repositories to export")
            return None

        owner = repos[0].owner_login if repos else "unknown"
        filename = filename or f"github_repos_{owner}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Name", "Full Name", "Description", "Language", "Stars", "Forks",
                    "Watchers", "Size (KB)", "Created At", "Updated At", "Pushed At",
                    "Fork", "Archived", "Private", "License", "Topics", "URL"
                ])

                for repo in repos:
                    writer.writerow([
                        repo.name,
                        repo.full_name,
                        repo.description or "",
                        repo.language or "",
                        repo.stars,
                        repo.forks,
                        repo.watchers,
                        repo.size_kb,
                        repo.created_at,
                        repo.updated_at,
                        repo.pushed_at,
                        "Yes" if repo.fork else "No",
                        "Yes" if repo.archived else "No",
                        "Yes" if repo.private else "No",
                        repo.license_name or "",
                        "; ".join(repo.topics) if repo.topics else "",
                        repo.html_url,
                    ])

            logger.info(f"Exported {len(repos)} repositories to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting repositories to CSV: {e}")
            return None

    def export_statistics(self, stats, filename: str = None) -> Optional[Path]:
        """Export user statistics to CSV."""
        if not stats:
            logger.warning("No statistics to export")
            return None

        filename = filename or f"github_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Metric", "Value"])
                writer.writerow(["Total Repositories", stats.total_repos])
                writer.writerow(["Total Stars", stats.total_stars])
                writer.writerow(["Total Forks", stats.total_forks])
                writer.writerow(["Total Watchers", stats.total_watchers])
                writer.writerow(["Total Size (KB)", stats.total_size_kb])
                writer.writerow(["Original Repos", stats.original_count])
                writer.writerow(["Forked Repos", stats.forked_count])
                writer.writerow(["Language Diversity", stats.language_diversity])
                writer.writerow(["Top Language", stats.top_language or ""])
                writer.writerow([])
                writer.writerow(["Language", "Repository Count"])

                for lang, count in stats.languages.items():
                    writer.writerow([lang, count])

                writer.writerow([])
                writer.writerow(["Top Repositories (by Stars)"])
                writer.writerow(["Name", "Stars", "Language", "URL"])

                for repo in stats.top_repos:
                    writer.writerow([repo.name, repo.stars, repo.language or "", repo.html_url])

            logger.info(f"Exported statistics to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting statistics to CSV: {e}")
            return None

    def export_events(self, events: List, filename: str = None) -> Optional[Path]:
        """Export events to CSV."""
        if not events:
            logger.warning("No events to export")
            return None

        filename = filename or f"github_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.export_dir / filename

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Type", "Repository", "Created At", "URL"])

                for event in events:
                    writer.writerow([
                        event.display_type,
                        event.repo_name,
                        event.created_at,
                        event.repo_url,
                    ])

            logger.info(f"Exported {len(events)} events to CSV: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting events to CSV: {e}")
            return None

    def export_user_profile_json(self, user, filename: str = None) -> Optional[Path]:
        """Export user profile to JSON."""
        if not user:
            logger.warning("No user data to export")
            return None

        filename = filename or f"github_profile_{user.login}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.export_dir / filename

        try:
            data = {
                "exported_at": datetime.now().isoformat(),
                "profile": {
                    "login": user.login,
                    "id": user.id,
                    "name": user.name,
                    "avatar_url": user.avatar_url,
                    "company": user.company,
                    "blog": user.blog,
                    "location": user.location,
                    "email": user.email,
                    "bio": user.bio,
                    "twitter_username": user.twitter_username,
                    "public_repos": user.public_repos,
                    "public_gists": user.public_gists,
                    "followers": user.followers,
                    "following": user.following,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                    "html_url": user.html_url,
                    "account_age_days": user.account_age_days,
                }
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported user profile to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting user profile to JSON: {e}")
            return None

    def export_repositories_json(self, repos: List, filename: str = None) -> Optional[Path]:
        """Export repositories to JSON."""
        if not repos:
            logger.warning("No repositories to export")
            return None

        owner = repos[0].owner_login if repos else "unknown"
        filename = filename or f"github_repos_{owner}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.export_dir / filename

        try:
            repo_list = []
            for repo in repos:
                repo_list.append({
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "description": repo.description,
                    "language": repo.language,
                    "stars": repo.stars,
                    "forks": repo.forks,
                    "watchers": repo.watchers,
                    "size_kb": repo.size_kb,
                    "created_at": repo.created_at,
                    "updated_at": repo.updated_at,
                    "pushed_at": repo.pushed_at,
                    "fork": repo.fork,
                    "archived": repo.archived,
                    "private": repo.private,
                    "license": repo.license_name,
                    "topics": repo.topics,
                    "url": repo.html_url,
                })

            data = {
                "exported_at": datetime.now().isoformat(),
                "owner": owner,
                "total_repos": len(repos),
                "repositories": repo_list
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(repos)} repositories to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting repositories to JSON: {e}")
            return None

    def export_statistics_json(self, stats, filename: str = None) -> Optional[Path]:
        """Export user statistics to JSON."""
        if not stats:
            logger.warning("No statistics to export")
            return None

        filename = filename or f"github_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.export_dir / filename

        try:
            data = {
                "exported_at": datetime.now().isoformat(),
                "statistics": {
                    "total_repos": stats.total_repos,
                    "total_stars": stats.total_stars,
                    "total_forks": stats.total_forks,
                    "total_watchers": stats.total_watchers,
                    "total_size_kb": stats.total_size_kb,
                    "original_count": stats.original_count,
                    "forked_count": stats.forked_count,
                    "language_diversity": stats.language_diversity,
                    "top_language": stats.top_language,
                    "languages": stats.languages,
                    "top_repos": [
                        {
                            "name": r.name,
                            "stars": r.stars,
                            "language": r.language,
                            "url": r.html_url,
                        }
                        for r in stats.top_repos
                    ]
                }
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported statistics to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting statistics to JSON: {e}")
            return None

    def export_events_json(self, events: List, filename: str = None) -> Optional[Path]:
        """Export events to JSON."""
        if not events:
            logger.warning("No events to export")
            return None

        filename = filename or f"github_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.export_dir / filename

        try:
            event_list = []
            for event in events:
                event_list.append({
                    "type": event.type,
                    "display_type": event.display_type,
                    "repo_name": event.repo_name,
                    "repo_url": event.repo_url,
                    "created_at": event.created_at,
                    "payload": event.payload,
                })

            data = {
                "exported_at": datetime.now().isoformat(),
                "total_events": len(events),
                "events": event_list
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(events)} events to JSON: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error exporting events to JSON: {e}")
            return None


def create_exporter(export_dir: Path = None) -> GitHubExporter:
    """Factory function to create exporter."""
    return GitHubExporter(export_dir) if export_dir else GitHubExporter()