from __future__ import annotations

import csv
import json

from pathlib import Path

from src.config import EXPORT_DIR
from src.logger import logger


class ProductExporter:

    def export_csv(
        self,
        products,
        filename="products.csv",
    ):

        file_path = EXPORT_DIR / filename

        fields = [
            "id",
            "name",
            "url",
            "current_price",
            "target_price",
            "lowest_price",
            "availability",
            "last_checked",
            "created_at",
        ]

        with open(
            file_path,
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fields,
            )

            writer.writeheader()

            for product in products:

                writer.writerow({field: product[field] for field in fields})

        logger.info(
            "CSV exported: %s",
            file_path,
        )

        return Path(file_path)

    def export_json(
        self,
        products,
        filename="products.json",
    ):

        file_path = EXPORT_DIR / filename

        data = [dict(product) for product in products]

        with open(
            file_path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False,
            )

        logger.info(
            "JSON exported: %s",
            file_path,
        )

        return Path(file_path)
