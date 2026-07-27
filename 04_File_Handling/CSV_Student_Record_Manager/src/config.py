from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FOLDER = BASE_DIR / "data"
REPORT_FOLDER = BASE_DIR / "reports"
LOG_FOLDER = BASE_DIR / "logs"

CSV_FILE = DATA_FOLDER / "students.csv"

CSV_HEADERS = [
    "Roll No",
    "Name",
    "Department",
    "Year",
    "Marks"
]