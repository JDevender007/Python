from __future__ import annotations

import requests

from src.config import (
    REQUEST_TIMEOUT,
)

from src.logger import logger


class NewsScraper:

    def __init__(self):

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/151.0 Safari/537.36"
                )
            }
        )

    def fetch_page(
        self,
        url,
    ):

        try:

            response = self.session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            logger.info(
                "Page fetched successfully: %s",
                url,
            )

            return response.text

        except requests.RequestException as error:

            logger.error(
                "Failed to fetch page: %s",
                error,
            )

            raise

    def close(self):

        self.session.close()
