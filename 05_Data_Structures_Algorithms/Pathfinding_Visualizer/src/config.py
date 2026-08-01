"""Application configuration values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Immutable configuration for layout and animation defaults."""

    title: str = "Pathfinding Visualizer"
    initial_width: int = 1280
    initial_height: int = 780
    minimum_width: int = 980
    minimum_height: int = 640
    control_panel_width: int = 330
    default_columns: int = 34
    min_columns: int = 16
    max_columns: int = 60
    row_ratio: float = 0.62
    default_animation_delay_ms: int = 16
    min_animation_delay_ms: int = 4
    max_animation_delay_ms: int = 120
    maze_density: float = 0.28
    window_padding: int = 14


CONFIG = AppConfig()
