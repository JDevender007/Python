from __future__ import annotations

import csv

from tkinter import filedialog

from src.utils import save_json


class NewsExporter:

    def export_csv(
        self,
        articles,
    ):

        file = filedialog.asksaveasfilename(
            title="Save CSV File",
            defaultextension=".csv",
            filetypes=[
                (
                    "CSV Files",
                    "*.csv",
                )
            ],
        )

        if not file:

            return None

        fields = [
            "title",
            "link",
            "date",
            "summary",
        ]

        with open(
            file,
            "w",
            newline="",
            encoding="utf-8",
        ) as output:

            writer = csv.DictWriter(
                output,
                fieldnames=fields,
            )

            writer.writeheader()

            writer.writerows(articles)

        return file

    def export_json(
        self,
        articles,
    ):

        file = filedialog.asksaveasfilename(
            title="Save JSON File",
            defaultextension=".json",
            filetypes=[
                (
                    "JSON Files",
                    "*.json",
                )
            ],
        )

        if not file:

            return None

        save_json(
            articles,
            file,
        )

        return file
