from pathlib import Path

from tqdm import tqdm

from config import SCAN_FOLDER
from hash_utils import calculate_hash
from logger import logger

class DuplicateFinder:

    def __init__(self):
        self.hash_map = {}
        self.duplicates = {}

    def scan_files(self):

        files = [file for file in SCAN_FOLDER.rglob("*") if file.is_file()]

        if not files:
            print("No files found.")
            return {}

        print(f"\nScanning {len(files)} files...\n")

        for file in tqdm(files, desc="Scanning"):

            if file.stat().st_size == 0:
                continue

            try:
                file_hash = calculate_hash(file)

                if file_hash in self.hash_map:
                    self.duplicates.setdefault(file_hash, []).append(file)
                else:
                    self.hash_map[file_hash] = file

            except Exception as error:
                logger.error(f"{file}: {error}")

        return self.duplicates

    def display_duplicates(self):

        if not self.duplicates:
            print("\nNo duplicate files found.")
            return

        print("\nDuplicate Files Found\n")

        count = 1

        for original_hash, duplicate_list in self.duplicates.items():

            print(f"Group {count}")

            print(f"Original : {self.hash_map[original_hash]}")

            for duplicate in duplicate_list:
                print(f"Duplicate: {duplicate}")

            print()

            count += 1

        logger.info(
            f"Duplicate scan completed. {len(self.duplicates)} duplicate groups found."
        )