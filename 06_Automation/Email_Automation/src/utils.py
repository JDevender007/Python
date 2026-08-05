from __future__ import annotations

import os
import platform
import subprocess

from pathlib import Path


def file_exists(path: str | Path) -> bool:

    return Path(path).exists()


def create_directory(path: str | Path):

    Path(path).mkdir(
        parents=True,
        exist_ok=True,
    )


def open_folder(path: str | Path):

    folder = Path(path)

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


def remove_duplicates(items: list[str]) -> list[str]:

    unique = []

    seen = set()

    for item in items:

        if item not in seen:

            unique.append(item)

            seen.add(item)

    return unique


def is_valid_email(email: str) -> bool:

    if "@" not in email:
        return False

    if "." not in email:
        return False

    return True


def split_emails(text: str) -> list[str]:

    emails = []

    for email in text.split(","):

        email = email.strip()

        if email:

            emails.append(email)

    return remove_duplicates(emails)
