from __future__ import annotations

import requests

from src.config import REQUEST_TIMEOUT
from src.logger import logger


class JobScraper:

    def __init__(self):

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/151.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,image/avif,"
                    "image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    def fetch_page(self, url):

        try:

            response = self.session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            response.raise_for_status()

            logger.info(
                "Page fetched successfully: %s",
                url,
            )

            return response.text

        except requests.HTTPError as error:

            logger.error(
                "HTTP error while fetching %s: %s",
                url,
                error,
            )

            raise

        except requests.RequestException as error:

            logger.error(
                "Request failed for %s: %s",
                url,
                error,
            )

            raise

    def close(self):

        self.session.close()
