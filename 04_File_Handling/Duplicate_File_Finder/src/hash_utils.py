import hashlib
from pathlib import Path

from config import CHUNK_SIZE

def calculate_hash(file_path: Path) -> str:
    """
    Calculate SHA-256 hash for a file.
    """

    sha = hashlib.sha256()

    with open(file_path, "rb") as file:
        while chunk := file.read(CHUNK_SIZE):
            sha.update(chunk)

    return sha.hexdigest()