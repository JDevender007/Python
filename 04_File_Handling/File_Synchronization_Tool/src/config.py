from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SOURCE_FOLDER = BASE_DIR / "source_folder"
DESTINATION_FOLDER = BASE_DIR / "destination_folder"

REPORT_FOLDER = BASE_DIR / "reports"
LOG_FOLDER = BASE_DIR / "logs"

CHUNK_SIZE = 8192
HASH_ALGORITHM = "sha256"