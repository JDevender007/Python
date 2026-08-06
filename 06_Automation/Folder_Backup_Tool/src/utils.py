from __future__ import annotations

import os
import shutil

from pathlib import Path


def create_directory(path):

    Path(path).mkdir(
        parents=True,
        exist_ok=True,
    )


def directory_exists(path):

    return Path(path).exists()


def get_folder_size(folder):

    total = 0

    for root, _, files in os.walk(folder):

        for file in files:

            file_path = Path(root) / file

            if file_path.exists():

                total += file_path.stat().st_size

    return total


def format_size(size):

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ]

    value = float(size)

    for unit in units:

        if value < 1024:

            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{value:.2f} PB"


def copy_file(source, destination):

    shutil.copy2(
        source,
        destination,
    )


def copy_directory(source, destination):

    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
    )


def current_timestamp():

    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
