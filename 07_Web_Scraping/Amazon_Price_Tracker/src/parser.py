from __future__ import annotations

from bs4 import BeautifulSoup

from src.utils import (
    clean_price,
    clean_text,
)


class AmazonParser:

    def parse(
        self,
        html,
    ):

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        name = self._get_name(soup)

        price_text = self._get_price(soup)

        availability = self._get_availability(soup)

        return {
            "name": name,
            "price": clean_price(price_text),
            "availability": availability,
        }

    def _get_name(
        self,
        soup,
    ):

        selectors = [
            "#productTitle",
            "h1.product-title",
            "h1",
        ]

        for selector in selectors:

            element = soup.select_one(selector)

            if element:

                value = clean_text(element.get_text())

                if value:

                    return value

        return "Unknown Product"

    def _get_price(
        self,
        soup,
    ):

        selectors = [
            "span.a-price span.a-offscreen",
            ".a-price-whole",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            ".priceToPay .a-offscreen",
            ".a-offscreen",
        ]

        for selector in selectors:

            element = soup.select_one(selector)

            if element:

                value = clean_text(element.get_text())

                if value:

                    return value

        return ""

    def _get_availability(
        self,
        soup,
    ):

        selectors = [
            "#availability",
            "#outOfStock",
        ]

        for selector in selectors:

            element = soup.select_one(selector)

            if element:

                value = clean_text(element.get_text())

                if value:

                    return value

        return "Unknown"
