from __future__ import annotations

import pandas as pd


class ReportGenerator:

    def __init__(self):

        self.summary = None

    def generate_summary(
        self,
        dataframe,
    ):

        self.summary = dataframe.describe(include="all")

        return self.summary

    def generate_missing_report(
        self,
        dataframe,
    ):

        report = pd.DataFrame()

        report["Column"] = dataframe.columns

        report["Missing Values"] = dataframe.isna().sum().values

        report["Data Type"] = dataframe.dtypes.values

        return report

    def generate_statistics(
        self,
        dataframe,
    ):

        return dataframe.describe()

    def export(
        self,
        dataframe,
        file,
    ):

        dataframe.to_excel(
            file,
            index=False,
        )
