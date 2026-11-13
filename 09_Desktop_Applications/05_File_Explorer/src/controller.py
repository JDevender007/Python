"""File Explorer controller - connects view and model."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
from .model import FileSystemModel, DirectoryNode
from .ui.view import ExplorerView


def init_file_explorer(view: ExplorerView) -> None:
    """Initialize the file explorer with view and model."""
    model = FileSystemModel()
    view.set_model(model)
    
    # Set initial path to home
    if model.current:
        path_str = model.current.get_path()
        view.path_var.set(path_str)


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