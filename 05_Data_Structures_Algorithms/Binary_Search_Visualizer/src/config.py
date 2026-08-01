"""Central configuration for the Binary Search Visualizer."""

from enum import Enum
from pathlib import Path

from .colors import ColorPalette

APP_NAME = "Binary Search Visualizer"
APP_VERSION = "1.0.0"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
LOG_FILE = PROJECT_ROOT / "binary_search_visualizer.log"

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820
MIN_WINDOW_WIDTH = 980
MIN_WINDOW_HEIGHT = 680

TARGET_FPS = 60
FRAME_INTERVAL_MS = max(1, round(1000 / TARGET_FPS))
DEFAULT_ANIMATION_DELAY_MS = 420
MIN_ANIMATION_DELAY_MS = 60
MAX_ANIMATION_DELAY_MS = 1200

DEFAULT_ARRAY_SIZE = 32
MIN_ARRAY_SIZE = 5
MAX_ARRAY_SIZE = 100
MIN_ARRAY_VALUE = 5
MAX_ARRAY_VALUE = 100

BAR_MIN_WIDTH = 3
BAR_MAX_WIDTH = 38
BAR_GAP_RATIO = 0.18
CANVAS_PADDING_X = 28
CANVAS_PADDING_TOP = 32
CANVAS_PADDING_BOTTOM = 54
GRID_LINE_COUNT = 5

PANEL_PADDING = 12
WIDGET_PADDING_X = 10
WIDGET_PADDING_Y = 7
SECTION_SPACING = 10
CONTROL_PANEL_WIDTH = 330

FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"
FONT_TITLE = (FONT_FAMILY, 22, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 12, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_BUTTON = (FONT_FAMILY, 10, "bold")
FONT_MONO_SMALL = (FONT_MONO, 9)

ALGORITHM_BINARY = "Binary Search"
ALGORITHM_LINEAR = "Linear Search"
ALGORITHMS = (ALGORITHM_BINARY, ALGORITHM_LINEAR)

PALETTE = ColorPalette()


class AppState(str, Enum):
    """Application lifecycle states used to manage controls safely."""

    IDLE = "Idle"
    RUNNING = "Running"
    PAUSED = "Paused"
    STOPPED = "Stopped"
    COMPLETED = "Completed"
