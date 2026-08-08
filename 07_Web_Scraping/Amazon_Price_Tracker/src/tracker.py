from __future__ import annotations

from src.database import Database
from src.logger import logger
from src.utils import generate_timestamp


class PriceTracker:

    def __init__(
        self,
        database,
    ):

        self.database = database

    def add_product(
        self,
        name,
        url,
        current_price,
        target_price,
        availability,
    ):

        timestamp = generate_timestamp()

        lowest_price = current_price

        product_id = self.database.add_product(
            name,
            url,
            current_price,
            target_price,
            lowest_price,
            availability,
            timestamp,
        )

        if current_price > 0:

            self.database.add_price_history(
                product_id,
                current_price,
                timestamp,
            )

        logger.info(
            "Started tracking: %s",
            name,
        )

        return product_id

    def update_product(
        self,
        product_id,
        current_price,
        availability,
    ):

        product = self.database.get_product(product_id)

        if not product:

            raise ValueError("Product not found.")

        old_lowest = product["lowest_price"]

        if old_lowest <= 0:

            lowest_price = current_price

        elif current_price <= 0:

            lowest_price = old_lowest

        else:

            lowest_price = min(
                old_lowest,
                current_price,
            )

        timestamp = generate_timestamp()

        self.database.update_product(
            product_id,
            current_price,
            lowest_price,
            availability,
            timestamp,
        )

        if current_price > 0:

            self.database.add_price_history(
                product_id,
                current_price,
                timestamp,
            )

        logger.info(
            "Product price updated: %s",
            product_id,
        )

    def is_target_reached(
        self,
        product_id,
    ):

        product = self.database.get_product(product_id)

        if not product:

            return False

        target = product["target_price"]

        current = product["current_price"]

        if target <= 0:

            return False

        if current <= 0:

            return False

        return current <= target

    def get_price_change(
        self,
        product_id,
    ):

        history = self.database.get_price_history(product_id)

        if len(history) < 2:

            return 0.0

        previous = history[-2]["price"]

        current = history[-1]["price"]

        if previous <= 0:

            return 0.0

        return ((current - previous) / previous) * 100
