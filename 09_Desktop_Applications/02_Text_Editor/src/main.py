"""Text Editor - A lightweight text editor built with Tkinter."""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# Import editor components
from src.model import EditorModel, Document
from src.services.file_service import FileService
from src.ui.view import EditorView
from src.controller import EditorController


def main() -> None:
    """Entry point for the Text Editor application."""
    root = tk.Tk()
    root.title("Text Editor - Python Portfolio")
    root.geometry("600x400")
    root.minsize(500, 300)
    root.maxsize(800, 600)

    # Create the editor controller (this sets up everything)
    editor = EditorController(root)

    root.mainloop()


if __name__ == "__main__":
    main()