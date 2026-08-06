from __future__ import annotations

from tkinter import filedialog

import pandas as pd


class ExcelHandler:

    def __init__(self):

        self.file = ""

        self.dataframe = None

    def open_file(self):

        file = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[
                (
                    "Excel Files",
                    "*.xlsx *.xls",
                )
            ],
        )

        if file:

            self.file = file

        return self.file

    def load(self):

        if not self.file:

            return None

        self.dataframe = pd.read_excel(self.file)

        return self.dataframe

    def save(
        self,
        dataframe,
    ):

        file = filedialog.asksaveasfilename(
            title="Save Excel File",
            defaultextension=".xlsx",
            filetypes=[
                (
                    "Excel Files",
                    "*.xlsx",
                )
            ],
        )

        if not file:

            return None

        dataframe.to_excel(
            file,
            index=False,
        )

        return file

    def get_dataframe(self):

        return self.dataframe
