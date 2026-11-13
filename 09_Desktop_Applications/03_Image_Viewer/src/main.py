"""Image Viewer - A desktop image viewer built with Tkinter and Pillow."""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# Import image viewer components
from src.model import ImageModel
from src.ui.view import ImageView
from src.controller import init_image_viewer, load_image_from_path


def main() -> None:
    """Entry point for the Image Viewer application."""
    root = tk.Tk()
    root.title("Image Viewer - Python Portfolio")
    root.geometry("800x600")
    root.minsize(640, 480)
    
    # Create the view
    viewer = ImageView(root)
    viewer.pack(fill="both", expand=True)
    
    # Initialize the controller (sets up model, wires events, etc.)
    init_image_viewer(viewer, root)
    
    # Load a sample image if available, otherwise show placeholder
    # The viewer is now ready for user interaction
    
    root.mainloop()


if __name__ == "__main__":
    main()