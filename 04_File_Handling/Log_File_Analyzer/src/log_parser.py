from pathlib import Path

from config import LOG_FOLDER
from config import SUPPORTED_EXTENSIONS

class LogParser:

    def load_logs(self):

        log_entries = []

        if not LOG_FOLDER.exists():
            return log_entries

        files = [
            file
            for file in LOG_FOLDER.iterdir()
            if file.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

        for file in files:

            with open(file, "r", encoding="utf-8") as log:

                for line in log:

                    line = line.strip()

                    if line:
                        log_entries.append(line)

        return log_entries