"""File Explorer - A lightweight Windows-friendly file explorer built with Tkinter and pathlib."""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# Import file explorer components
from src.model import FileSystemModel
from src.ui.view import ExplorerView
from src.controller import init_file_explorer, main


def main() -> None:
    """Entry point for the File Explorer application."""
    root = tk.Tk()
    root.title("File Explorer - Python Portfolio")
    root.geometry("800x600")
    root.minsize(640, 400)
    
    # Create the view
    view = ExplorerView(root)
    view.pack(fill="both", expand=True)
    
    # Initialize the explorer
    init_file_explorer(view)
    
    root.mainloop()


if __name__ == "__main__":
    main()