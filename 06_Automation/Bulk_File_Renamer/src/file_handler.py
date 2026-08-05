from __future__ import annotations

from pathlib import Path

from tkinter import filedialog

from src.config import DEFAULT_DIRECTORY
from src.config import SUPPORTED_FILES

from src.utils import (
    remove_duplicates,
    sort_files,
)


class FileHandler:

    def __init__(self):

        self.current_folder = ""

        self.files = []

    def select_folder(self) -> str | None:

        folder = filedialog.askdirectory(
            title="Select Folder",
            initialdir=DEFAULT_DIRECTORY,
        )

        if folder:

            self.current_folder = folder

            self.load_files()

            return folder

        return None

    def load_files(self):

        self.files.clear()

        if not self.current_folder:
            return

        folder = Path(self.current_folder)

        for item in folder.iterdir():

            if item.is_file():

                self.files.append(str(item))

        self.files = remove_duplicates(self.files)

        self.files = sort_files(self.files)

    def refresh(self):

        self.load_files()

    def get_files(self) -> list[str]:

        return self.files.copy()

    def get_folder(self) -> str:

        return self.current_folder

    def total_files(self) -> int:

        return len(self.files)

    def is_empty(self) -> bool:

        return len(self.files) == 0

    def clear(self):

        self.files.clear()

    def exists(self, path: str) -> bool:

        return Path(path).exists()
