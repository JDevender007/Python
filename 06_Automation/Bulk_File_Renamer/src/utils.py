from __future__ import annotations

import os
import platform
import subprocess

from pathlib import Path


def format_file_size(size: int) -> str:

    units = ["B", "KB", "MB", "GB", "TB"]

    value = float(size)

    for unit in units:

        if value < 1024:
            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{value:.2f} PB"


def get_filename(path: str | Path) -> str:

    return Path(path).name


def get_extension(path: str | Path) -> str:

    return Path(path).suffix


def get_stem(path: str | Path) -> str:

    return Path(path).stem


def get_file_size(path: str | Path) -> int:

    return Path(path).stat().st_size


def get_file_size_string(path: str | Path) -> str:

    return format_file_size(get_file_size(path))


def file_exists(path: str | Path) -> bool:

    return Path(path).exists()


def is_file(path: str | Path) -> bool:

    return Path(path).is_file()


def is_directory(path: str | Path) -> bool:

    return Path(path).is_dir()


def create_directory(path: str | Path) -> None:

    Path(path).mkdir(
        parents=True,
        exist_ok=True,
    )


def open_folder(folder: str | Path) -> None:

    folder = Path(folder)

    if not folder.exists():
        return

    system = platform.system()

    if system == "Windows":

        os.startfile(folder)

    elif system == "Darwin":

        subprocess.run(
            ["open", str(folder)],
            check=False,
        )

    else:

        subprocess.run(
            ["xdg-open", str(folder)],
            check=False,
        )


def remove_duplicates(files: list[str]) -> list[str]:

    unique = []

    seen = set()

    for file in files:

        if file not in seen:

            seen.add(file)

            unique.append(file)

    return unique


def sort_files(files: list[str]) -> list[str]:

    return sorted(
        files,
        key=lambda file: Path(file).name.lower(),
    )
