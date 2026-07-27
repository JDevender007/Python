import shutil
from pathlib import Path

from config import INPUT_FOLDER, OUTPUT_FOLDER
from utils import get_category
from logger import logger

class FileOrganizer:

    def organize(self):

        if not INPUT_FOLDER.exists():
            print("Input folder not found.")
            return

        files = [file for file in INPUT_FOLDER.iterdir() if file.is_file()]

        if not files:
            print("No files found.")
            return

        for file in files:

            category = get_category(file)

            destination = OUTPUT_FOLDER / category
            destination.mkdir(parents=True, exist_ok=True)

            target = destination / file.name

            counter = 1

            while target.exists():

                target = destination / f"{file.stem}_{counter}{file.suffix}"
                counter += 1

            shutil.move(file, target)

            logger.info(f"{file.name} moved to {category}")

            print(f"Moved: {file.name} -> {category}")

        print("\nOrganization Completed Successfully.")