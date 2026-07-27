from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FOLDER = BASE_DIR / "input_files"
OUTPUT_FOLDER = BASE_DIR / "organized_files"
LOG_FOLDER = BASE_DIR / "logs"

SUPPORTED_EXTENSIONS = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp"],
    "Documents": [".pdf", ".docx", ".txt", ".pptx", ".xlsx"],
    "Videos": [".mp4", ".mkv", ".avi"],
    "Music": [".mp3", ".wav"],
    "Archives": [".zip", ".rar", ".7z"],
    "Python": [".py"],
    "Others": []
}