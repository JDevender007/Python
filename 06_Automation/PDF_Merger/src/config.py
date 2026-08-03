"""
Application configuration.

This module stores all application constants.
"""

from pathlib import Path

APP_NAME = "PDF Merger"
APP_VERSION = "1.0.0"

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 750
MIN_WIDTH = 1000
MIN_HEIGHT = 650

WINDOW_TITLE = f"{APP_NAME} v{APP_VERSION}"

FONT_FAMILY = "Segoe UI"

TITLE_FONT = (FONT_FAMILY, 18, "bold")
HEADING_FONT = (FONT_FAMILY, 13, "bold")
TEXT_FONT = (FONT_FAMILY, 11)
BUTTON_FONT = (FONT_FAMILY, 10, "bold")
STATUS_FONT = (FONT_FAMILY, 10)

PAD_X = 10
PAD_Y = 10

BUTTON_WIDTH = 18

DEFAULT_OUTPUT_NAME = "merged.pdf"

DEFAULT_OUTPUT_DIR = Path.home() / "Documents"

PDF_FILE_TYPES = [
    ("PDF Files", "*.pdf"),
    ("All Files", "*.*"),
]

FULLSCREEN = False
RESIZABLE = True

PROGRESS_MIN = 0
PROGRESS_MAX = 100