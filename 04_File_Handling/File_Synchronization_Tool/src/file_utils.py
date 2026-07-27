import hashlib
from pathlib import Path

from config import CHUNK_SIZE

def calculate_hash(file_path: Path) -> str:
    """
    Calculate SHA-256 hash of a file.
    """

    sha = hashlib.sha256()

    with open(file_path, "rb") as file:

        while chunk := file.read(CHUNK_SIZE):
            sha.update(chunk)

    return sha.hexdigest()


def files_are_different(source: Path, destination: Path) -> bool:
    """
    Compare two files using SHA-256 hashes.
    """

    if not destination.exists():
        return True

    return calculate_hash(source) != calculate_hash(destination)