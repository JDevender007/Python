from __future__ import annotations

import csv

from tkinter import filedialog

from src.utils import save_json


class JobExporter:

    fields = [
        "title",
        "company",
        "location",
        "description",
        "link",
    ]

    def export_csv(
        self,
        jobs,
    ):

        file = filedialog.asksaveasfilename(
            title="Save Job Listings",
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

        with open(
            file,
            "w",
            newline="",
            encoding="utf-8",
        ) as output:

            writer = csv.DictWriter(
                output,
                fieldnames=self.fields,
            )

            writer.writeheader()

            writer.writerows(jobs)

        return file

    def export_json(
        self,
        jobs,
    ):

        file = filedialog.asksaveasfilename(
            title="Save Job Listings",
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
            jobs,
            file,
        )

        return file
