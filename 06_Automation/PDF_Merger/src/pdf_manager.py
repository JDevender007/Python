from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from utils import (
    get_filename,
    get_filesize_string,
    get_page_count,
)

class PDFManager:

    def __init__(self) -> None:
        self.pdf_files: list[str] = []

    def load_files(self, files: list[str]) -> None:
        self.pdf_files = files.copy()

    def add_file(self, file: str) -> None:
        if file not in self.pdf_files:
            self.pdf_files.append(file)

    def remove_file(self, index: int) -> None:
        if 0 <= index < len(self.pdf_files):
            self.pdf_files.pop(index)

    def clear(self) -> None:
        self.pdf_files.clear()

    def get_files(self) -> list[str]:
        return self.pdf_files.copy()

    def total_files(self) -> int:
        return len(self.pdf_files)

    def total_pages(self) -> int:
        pages = 0

        for pdf in self.pdf_files:
            pages += get_page_count(pdf)

        return pages

    def total_size(self) -> str:
        total = 0

        for pdf in self.pdf_files:
            total += Path(pdf).stat().st_size

        units = ["B", "KB", "MB", "GB"]

        value = float(total)

        for unit in units:
            if value < 1024:
                return f"{value:.2f} {unit}"
            value /= 1024

        return f"{value:.2f} TB"

    def get_metadata(self) -> list[dict]:
        metadata = []

        for pdf in self.pdf_files:

            item = {
                "name": get_filename(pdf),
                "path": pdf,
                "pages": get_page_count(pdf),
                "size": get_filesize_string(pdf),
            }

            metadata.append(item)

        return metadata

    def get_reader(self, pdf: str) -> PdfReader:
        return PdfReader(pdf)

    def is_empty(self) -> bool:
        return len(self.pdf_files) == 0

    def file_names(self) -> list[str]:
        return [get_filename(pdf) for pdf in self.pdf_files]

    def page_counts(self) -> list[int]:
        return [get_page_count(pdf) for pdf in self.pdf_files]

    def file_sizes(self) -> list[str]:
        return [get_filesize_string(pdf) for pdf in self.pdf_files]

    def summary(self) -> dict:
        return {
            "files": self.total_files(),
            "pages": self.total_pages(),
            "size": self.total_size(),
        }