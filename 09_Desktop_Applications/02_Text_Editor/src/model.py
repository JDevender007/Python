"""Text Editor model - manages the document state and operations."""

from __future__ import annotations
import os
import pathlib
from datetime import datetime
from typing import Optional, List, Tuple


class Document:
    """Represents a text document with undo/redo support."""

    def __init__(self, filepath: Optional[pathlib.Path] = None) -> None:
        self.filepath: Optional[pathlib.Path] = filepath
        self.title: str = "Untitled"
        self.content: str = ""
        self._undo_stack: List[str] = []
        self._redo_stack: List[str] = []
        self._modified: bool = False
        self._read_only: bool = False

        if filepath and filepath.exists():
            self.open(filepath)

    def open(self, filepath: pathlib.Path) -> bool:
        """Open a file and set as current document."""
        try:
            self.filepath = pathlib.Path(filepath)
            with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
                self.content = f.read()
            self.title = self.filepath.name
            self._modified = False
            self._clear_undo_redo()
            return True
        except (FileNotFoundError, PermissionError, OSError) as e:
            raise IOError(f"Could not open file: {e}")
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(self.filepath, "r", encoding="latin-1", errors="replace") as f:
                    self.content = f.read()
                self.title = self.filepath.name
                self._modified = False
                self._clear_undo_redo()
                return True
            except Exception:
                raise IOError("Could not decode file with any supported encoding")

    def save(self, filepath: Optional[pathlib.Path] = None) -> bool:
        """Save the document to file."""
        target = filepath or self.filepath
        if not target:
            return False

        try:
            with open(pathlib.Path(target), "w", encoding="utf-8") as f:
                f.write(self.content)
            self.filepath = pathlib.Path(target)
            self.title = self.filepath.name
            self._modified = False
            self._clear_undo_redo()
            return True
        except (PermissionError, OSError) as e:
            raise IOError(f"Could not save file: {e}")

    def save_as(self, filepath: pathlib.Path) -> bool:
        """Save the document as a new file."""
        try:
            self.filepath = pathlib.Path(filepath)
            return self.save(self.filepath)
        except Exception:
            return False

    def undo(self) -> bool:
        """Undo the last change."""
        if not self._undo_stack or self._read_only:
            return False
        self._redo_stack.append(self.content)
        self.content = self._undo_stack.pop()
        self._modified = self.content != self._get_initial_content()
        return True

    def redo(self) -> bool:
        """Redo the last undone change."""
        if not self._redo_stack or self._read_only:
            return False
        self._undo_stack.append(self.content)
        self.content = self._redo_stack.pop()
        self._modified = self.content != self._get_initial_content()
        return True

    def _clear_undo_redo(self) -> None:
        """Clear undo and redo stacks."""
        self._undo_stack = []
        self._redo_stack = []

    def _get_initial_content(self) -> str:
        """Get the content state at last save."""
        if self.filepath:
            try:
                with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception:
                return self.content
        return self.content

    def set_modified(self, modified: bool = True) -> None:
        """Mark document as modified."""
        self._modified = modified

    def is_modified(self) -> bool:
        """Check if document has unsaved changes."""
        return self._modified

    def toggle_read_only(self) -> None:
        """Toggle read-only mode."""
        self._read_only = not self._read_only

    def is_read_only(self) -> bool:
        """Check if document is read-only."""
        return self._read_only

    def get_stats(self) -> Tuple[int, int, int]:
        """Get word count, char count, line count."""
        words = len(self.content.split()) if self.content.strip() else 0
        chars = len(self.content)
        lines = len(self.content.splitlines())
        return words, chars, lines


class EditorModel:
    """Manages the overall editor state including multiple documents."""

    def __init__(self) -> None:
        self.current_document: Optional[Document] = None
        self.documents: dict[str, Document] = {}
        self.recent_files: list[str] = []
        self.max_recent_files: int = 5
        self.word_wrap: bool = False
        self.font_size: int = 12
        self.theme: str = "light"

    def new_document(self) -> Document:
        """Create a new document."""
        doc = Document()
        doc_title = f"Untitled {len(self.documents) + 1}"
        doc.title = doc_title
        self.current_document = doc
        self.documents[doc_title] = doc
        return doc

    def open_document(self, filepath: pathlib.Path) -> Optional[Document]:
        """Open an existing document."""
        try:
            doc = Document(filepath)
            title = doc.title
            self.documents[title] = doc
            self.recent_files.insert(0, str(filepath))
            # Keep only recent files list manageable
            self.recent_files = self.recent_files[: self.max_recent_files]
            self.current_document = doc
            return doc
        except IOError:
            return None

    def close_document(self, doc: Document) -> bool:
        """Close a document with unsaved changes check."""
        if doc.is_modified():
            # In a real app, show a dialog question
            # For now, just close if user confirms
            pass
        title = doc.title
        if title in self.documents:
            del self.documents[title]
        if self.current_document is doc:
            self.current_document = None
        return True

    def set_current_document(self, doc: Document) -> None:
        """Set the current document."""
        self.current_document = doc

    def add_recent_file(self, filepath: str) -> None:
        """Add a file to recent files list."""
        self.recent_files.insert(0, filepath)
        self.recent_files = self.recent_files[: self.max_recent_files]

    def get_recent_files(self) -> list[str]:
        """Get the list of recent files."""
        return self.recent_files