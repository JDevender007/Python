from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

LOG_FOLDER = BASE_DIR / "sample_logs"
REPORT_FOLDER = BASE_DIR / "reports"
APP_LOG_FOLDER = BASE_DIR / "logs"

SUPPORTED_EXTENSIONS = [".log", ".txt"]