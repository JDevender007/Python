import shutil
from pathlib import Path

from tqdm import tqdm

from config import SOURCE_FOLDER
from config import DESTINATION_FOLDER

from file_utils import files_are_different
from logger import logger

class FileSynchronizer:

    def __init__(self):

        self.synced_files = []

    def synchronize(self):

        if not SOURCE_FOLDER.exists():

            print("Source folder not found.")
            return

        files = [file for file in SOURCE_FOLDER.rglob("*") if file.is_file()]

        if not files:

            print("No files found.")
            return

        print(f"\nSynchronizing {len(files)} files...\n")

        for source_file in tqdm(files):

            relative_path = source_file.relative_to(SOURCE_FOLDER)

            destination_file = DESTINATION_FOLDER / relative_path

            destination_file.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            try:

                if files_are_different(source_file, destination_file):

                    shutil.copy2(source_file, destination_file)

                    self.synced_files.append(
                        (
                            str(source_file),
                            str(destination_file)
                        )
                    )

                    logger.info(
                        f"Copied: {source_file}"
                    )

            except Exception as error:

                logger.error(
                    f"{source_file}: {error}"
                )

        print(
            f"\nSynchronization Complete."
        )

        print(
            f"Files Copied/Updated: {len(self.synced_files)}"
        )