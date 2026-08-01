"""Application entry point for Graph Traversal Visualizer."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.colors import Colors
from src.config import AppConfig
from src.logger import configure_logging
from src.utils import center_window
from src.visualizer import GraphTraversalVisualizer


def main() -> int:
    """Create the root window and start the Tk event loop."""
    logger = configure_logging()
    config = AppConfig()
    root: tk.Tk | None = None

    try:
        root = tk.Tk()
        root.title(config.window.title)
        root.configure(bg=Colors.BACKGROUND)
        root.minsize(config.window.min_width, config.window.min_height)
        center_window(root, config.window.width, config.window.height)
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        GraphTraversalVisualizer(root, config)
        logger.info("Application started")
        root.mainloop()
        logger.info("Application closed")
        return 0
    except tk.TclError as exc:
        logger.exception("Tkinter could not initialize")
        if root is not None:
            try:
                messagebox.showerror(
                    "Graph Traversal Visualizer",
                    f"The application could not start:\n\n{exc}",
                    parent=root,
                )
            except tk.TclError:
                pass
        return 1
    except Exception as exc:  # noqa: BLE001 - top-level crash boundary
        logger.exception("Unhandled application error")
        if root is not None:
            try:
                messagebox.showerror(
                    "Unexpected Error",
                    f"An unexpected error occurred:\n\n{exc}",
                    parent=root,
                )
            except tk.TclError:
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
