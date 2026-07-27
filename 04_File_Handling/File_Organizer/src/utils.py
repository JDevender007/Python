from pathlib import Path
from config import SUPPORTED_EXTENSIONS

def get_category(file_path: Path) -> str:
    extension = file_path.suffix.lower()

    for category, extensions in SUPPORTED_EXTENSIONS.items():
        if extension in extensions:
            return category

    return "Others"