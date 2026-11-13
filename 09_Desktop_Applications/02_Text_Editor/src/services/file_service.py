"""Text editor file service - handles all file operations."""

from __future__ import annotations
import os
import pathlib
from typing import Optional, List, Tuple
from .model import Document


class FileService:
    """Handles file operations for the text editor."""

    def __init__(self, model: "EditorModel") -> None:
        self.model = model

    def open_file(self, filepath: pathlib.Path) -> Optional[Document]:
        """Open a file and return the document."""
        doc = self.model.open_document(filepath)
        if doc:
            self.model.add_recent_file(str(filepath))
        return doc

    def save_current(self) -> bool:
        """Save the current document."""
        if self.model.current_document is None:
            return False
        doc = self.model.current_document
        if doc.filepath is None:
            return self.save_as_current()
        return doc.save(doc.filepath)

    def save_as_current(self) -> bool:
        """Save current document as a new file."""
        if self.model.current_document is None:
            return False
        doc = self.model.current_document
        # In a real app, show a file dialog
        # For this demo, use a default path
        default_path = pathlib.Path.home() / "Documents" / f"{doc.title}.txt"
        return doc.save_as(default_path)

    def new_file(self) -> Optional[Document]:
        """Create a new document."""
        return self.model.new_document()

    def close_current(self) -> bool:
        """Close the current document."""
        if self.model.current_document is None:
            return True
        return self.model.close_document(self.model.current_document)

    def get_current_title(self) -> str:
        """Get the current document title."""
        if self.model.current_document is None:
            return "Untitled"
        return self.model.current_document.title

    def get_stats(self) -> Tuple[int, int, int]:
        """Get document statistics."""
        if self.model.current_document is None:
            return (0, 0, 0)
        return self.model.current_document.get_stats()

    def toggle_read_only(self) -> None:
        """Toggle read-only mode for current document."""
        if self.model.current_document is not None:
            self.model.current_document.toggle_read_only()

    def is_read_only(self) -> bool:
        """Check if current document is read-only."""
        if self.model.current_document is not None:
            return self.model.current_document.is_read_only()
        return False

    def check_unsaved_changes(self) -> bool:
        """Check if current document has unsaved changes."""
        if self.model.current_document is None:
            return False
        return self.model.current_document.is_modified()