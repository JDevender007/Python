from __future__ import annotations

import shutil

from pathlib import Path

from src.logger import logger

from src.utils import (
    create_directory,
    current_timestamp,
)


class BackupManager:

    def __init__(self):

        self.history = []

    def create_backup(
        self,
        source,
        destination,
    ):

        source = Path(source)

        destination = Path(destination)

        if not source.exists():

            raise FileNotFoundError("Source folder not found.")

        backup_folder = destination / f"{source.name}_{current_timestamp()}"

        create_directory(
            backup_folder,
        )

        shutil.copytree(
            source,
            backup_folder,
            dirs_exist_ok=True,
        )

        self.history.append(
            (
                str(source),
                str(backup_folder),
            )
        )

        logger.info(
            "Backup created: %s",
            backup_folder,
        )

        return backup_folder

    def verify_backup(
        self,
        source,
        backup,
    ):

        source_files = list(Path(source).rglob("*"))

        backup_files = list(Path(backup).rglob("*"))

        return len(source_files) == len(backup_files)

    def get_history(self):

        return self.history.copy()

    def clear_history(self):

        self.history.clear()
