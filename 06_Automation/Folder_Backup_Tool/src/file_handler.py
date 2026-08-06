from __future__ import annotations

from pathlib import Path

from tkinter import filedialog


class FileHandler:

    def __init__(self):

        self.source_folder = ""

        self.destination_folder = ""

    def select_source(self):

        folder = filedialog.askdirectory(title="Select Source Folder")

        if folder:

            self.source_folder = folder

        return self.source_folder

    def select_destination(self):

        folder = filedialog.askdirectory(title="Select Backup Folder")

        if folder:

            self.destination_folder = folder

        return self.destination_folder

    def get_source(self):

        return self.source_folder

    def get_destination(self):

        return self.destination_folder

    def has_source(self):

        return Path(self.source_folder).exists()

    def has_destination(self):

        return Path(self.destination_folder).exists()

    def clear(self):

        self.source_folder = ""

        self.destination_folder = ""

    def get_total_files(self):

        if not self.has_source():

            return 0

        return len(
            [file for file in Path(self.source_folder).rglob("*") if file.is_file()]
        )

    def get_total_folders(self):

        if not self.has_source():

            return 0

        return len(
            [
                folder
                for folder in Path(self.source_folder).rglob("*")
                if folder.is_dir()
            ]
        )
