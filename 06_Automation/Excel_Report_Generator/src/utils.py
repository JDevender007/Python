from __future__ import annotations

from pathlib import Path

import pandas as pd


def file_exists(path):

    return Path(path).exists()


def create_directory(path):

    Path(path).mkdir(
        parents=True,
        exist_ok=True,
    )


def get_sheet_names(file):

    workbook = pd.ExcelFile(file)

    return workbook.sheet_names


def dataframe_shape(dataframe):

    return dataframe.shape


def dataframe_columns(dataframe):

    return list(dataframe.columns)


def dataframe_summary(dataframe):

    return dataframe.describe(include="all")


def save_dataframe(
    dataframe,
    output_file,
):

    dataframe.to_excel(
        output_file,
        index=False,
    )
