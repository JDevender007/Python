from __future__ import annotations

import matplotlib.pyplot as plt


class ChartGenerator:

    def create_bar_chart(
        self,
        dataframe,
        column,
    ):

        figure = plt.figure(figsize=(8, 5))

        dataframe[column].value_counts().plot(kind="bar")

        plt.title(column)

        plt.tight_layout()

        return figure

    def create_pie_chart(
        self,
        dataframe,
        column,
    ):

        figure = plt.figure(figsize=(6, 6))

        dataframe[column].value_counts().plot(
            kind="pie",
            autopct="%1.1f%%",
        )

        plt.ylabel("")

        plt.tight_layout()

        return figure

    def save_chart(
        self,
        figure,
        file,
    ):

        figure.savefig(
            file,
            dpi=300,
            bbox_inches="tight",
        )

        plt.close(figure)
