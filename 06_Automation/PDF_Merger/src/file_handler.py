"""
File handling module for PDF Merger.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from tkinter import messagebox

from config import DEFAULT_OUTPUT_DIR
from config import DEFAULT_OUTPUT_NAME
from config import PDF_FILE_TYPES

from utils import (
    remove_duplicates,
    validate_pdf_list,
)

class FileHandler:
    """
    Handles selecting, managing, and saving PDF files.
    """

    def __init__(self) -> None:
        self.pdf_files: list[str] = []

    def select_pdf_files(self) -> list[str]:
        """
        Open file picker and add PDF files.
        """

        files = filedialog.askopenfilenames(
            title="Select PDF Files",
            filetypes=PDF_FILE_TYPES,
        )

        if not files:
            return self.pdf_files

        self.pdf_files.extend(files)

        self.pdf_files = remove_duplicates(self.pdf_files)
        self.pdf_files = validate_pdf_list(self.pdf_files)

        return self.pdf_files

    def remove_file(self, index: int) -> None:
        """
        Remove a PDF using its index.
        """

        if 0 <= index < len(self.pdf_files):
            self.pdf_files.pop(index)

    def clear_files(self) -> None:
        """
        Remove every PDF.
        """

        self.pdf_files.clear()

    def move_up(self, index: int) -> int:
        """
        Move a PDF one position upward.
        """

        if index <= 0:
            return index

        self.pdf_files[index - 1], self.pdf_files[index] = (
            self.pdf_files[index],
            self.pdf_files[index - 1],
        )

        return index - 1

    def move_down(self, index: int) -> int:
        """
        Move a PDF one position downward.
        """

        if index >= len(self.pdf_files) - 1:
            return index

        self.pdf_files[index + 1], self.pdf_files[index] = (
            self.pdf_files[index],
            self.pdf_files[index + 1],
        )

        return index + 1

    def choose_output_file(self) -> str | None:
        """
        Ask user where to save merged PDF.
        """

        filename = filedialog.asksaveasfilename(
            title="Save Merged PDF",
            initialdir=DEFAULT_OUTPUT_DIR,
            initialfile=DEFAULT_OUTPUT_NAME,
            defaultextension=".pdf",
            filetypes=PDF_FILE_TYPES,
        )

        if filename:
            return filename

        return None

    def choose_output_folder(self) -> str | None:
        """
        Ask user to select output folder.
        """

        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=DEFAULT_OUTPUT_DIR,
        )

        if folder:
            return folder

        return None

    def get_files(self) -> list[str]:
        """
        Return all selected PDFs.
        """

        return self.pdf_files.copy()

    def count(self) -> int:
        """
        Return total PDFs.
        """

        return len(self.pdf_files)

    def is_empty(self) -> bool:
        """
        Return True if no PDFs exist.
        """

        return len(self.pdf_files) == 0

    def exists(self, pdf: str) -> bool:
        """
        Check if a PDF is already loaded.
        """

        return pdf in self.pdf_files

    def validate_before_merge(self) -> bool:
        """
        Ensure at least two PDFs are selected.
        """

        if len(self.pdf_files) < 2:
            messagebox.showwarning(
                "PDF Merger",
                "Please select at least two PDF files.",
            )
            return False

        return True

    @staticmethod
    def output_exists(path: str) -> bool:
        """
        Check whether output file already exists.
        """

        return Path(path).exists()