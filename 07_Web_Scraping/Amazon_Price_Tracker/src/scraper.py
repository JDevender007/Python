from __future__ import annotations

import requests

from src.config import REQUEST_TIMEOUT
from src.logger import logger


class AmazonScraper:

    def __init__(self):

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/151.0.0.0 "
                    "Safari/537.36"
                ),
                "Accept": (
                    "text/html,"
                    "application/xhtml+xml,"
                    "application/xml;q=0.9,"
                    "image/avif,"
                    "image/webp,"
                    "*/*;q=0.8"
                ),
                "Accept-Language": ("en-US,en;q=0.9"),
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    def fetch(
        self,
        url,
    ):

        logger.info(
            "Fetching product page: %s",
            url,
        )

        response = self.session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        if response.status_code == 403:

            raise PermissionError(
                "Amazon refused the request. " "The website returned HTTP 403."
            )

        response.raise_for_status()

        return response.text

    def close(self):

        self.session.close()
