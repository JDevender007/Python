"""Image Viewer controller - connects view and model."""

from __future__ import annotations
from pathlib import Path
from typing import Callable, Optional
from .model import ImageModel, ImageInfo
from .ui.view import ImageView


def init_image_viewer(viewer_view: ImageView, root: tk.Tk) -> None:
    """Initialize the image viewer with view and model."""
    model = ImageModel()
    viewer_view.set_viewer(model)
    
    # Wire up view callbacks
    # The view's button commands call model functions
    # and update the view display
    
    # Initialize with no image
    viewer_view._update_info_label(None)


def load_image_from_path(viewer_view: ImageView, filepath: Path) -> None:
    """Load an image from the given file path."""
    try:
        info = viewer_view._load_image(filepath)
        viewer_view._display_image()
        viewer_view._update_info_label(info)
    except ValueError as e:
        messagebox.showerror("Error", str(e))


def main() -> None:
    """Entry point for the Image Viewer application."""
    root = tk.Tk()
    root.title("Image Viewer - Python Portfolio")
    root.geometry("800x600")
    root.minsize(640, 480)
    
    # Create view and model
    viewer = ImageView(root)
    viewer.pack(fill="both", expand=True)
    
    # Initialize
    from src.controller import init_image_viewer, load_image_from_path
    init_image_viewer(viewer, root)
    
    root.mainloop()


if __name__ == "__main__":
    main()