"""
Utility functions for the PDF Merger application.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from pypdf import PdfReader

def format_file_size(size: int) -> str:
    """
    Convert bytes into a human-readable string.

    Parameters
    ----------
    size : int
        File size in bytes.

    Returns
    -------
    str
        Formatted file size.
    """

    units = ["B", "KB", "MB", "GB", "TB"]

    value = float(size)

    for unit in units:
        if value < 1024:
            return f"{value:.2f} {unit}"
        value /= 1024

    return f"{value:.2f} PB"

def get_page_count(pdf_path: str | Path) -> int:
    """
    Return the number of pages in a PDF.

    Parameters
    ----------
    pdf_path : str | Path

    Returns
    -------
    int
    """

    reader = PdfReader(str(pdf_path))
    return len(reader.pages)

def is_pdf(pdf_path: str | Path) -> bool:
    """
    Check whether the file is a valid PDF.

    Parameters
    ----------
    pdf_path : str | Path

    Returns
    -------
    bool
    """

    path = Path(pdf_path)

    if not path.exists():
        return False

    return path.suffix.lower() == ".pdf"

def file_exists(path: str | Path) -> bool:
    """
    Check if a file exists.
    """

    return Path(path).exists()

def get_filename(path: str | Path) -> str:
    """
    Return only the file name.
    """

    return Path(path).name

def get_filesize(path: str | Path) -> int:
    """
    Return file size in bytes.
    """

    return Path(path).stat().st_size

def get_filesize_string(path: str | Path) -> str:
    """
    Return formatted file size.
    """

    return format_file_size(get_filesize(path))

def open_folder(folder: str | Path) -> None:
    """
    Open a folder in the operating system.
    """

    folder = Path(folder)

    if not folder.exists():
        return

    system = platform.system()

    if system == "Windows":
        os.startfile(folder)

    elif system == "Darwin":
        subprocess.run(["open", str(folder)], check=False)

    else:
        subprocess.run(["xdg-open", str(folder)], check=False)

def create_directory(path: str | Path) -> None:
    """
    Create directory if it does not exist.
    """

    Path(path).mkdir(parents=True, exist_ok=True)

def remove_duplicates(paths: list[str]) -> list[str]:
    """
    Remove duplicate file paths while preserving order.
    """

    unique = []

    seen = set()

    for item in paths:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    return unique

def validate_pdf_list(paths: list[str]) -> list[str]:
    """
    Return only valid PDF files.
    """

    valid = []

    for path in paths:
        if is_pdf(path):
            valid.append(path)

    return valid

def sort_by_filename(paths: list[str]) -> list[str]:
    """
    Sort PDF files alphabetically.
    """

    return sorted(paths, key=lambda x: Path(x).name.lower())

def total_pages(paths: list[str]) -> int:
    """
    Calculate total pages from multiple PDFs.
    """

    pages = 0

    for pdf in paths:
        pages += get_page_count(pdf)

    return pages

def total_size(paths: list[str]) -> str:
    """
    Calculate total size of selected PDFs.
    """

    size = 0

    for pdf in paths:
        size += get_filesize(pdf)

    return format_file_size(size)