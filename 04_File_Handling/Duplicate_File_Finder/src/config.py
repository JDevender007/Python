from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SCAN_FOLDER = BASE_DIR / "duplicate_files"
REPORT_FOLDER = BASE_DIR / "reports"
LOG_FOLDER = BASE_DIR / "logs"

HASH_ALGORITHM = "sha256"
CHUNK_SIZE = 8192