"""Application configuration for Stack Queue Simulator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Centralized immutable application configuration."""

    title: str = "Stack & Queue Simulator"
    window_width: int = 1440
    window_height: int = 860
    minimum_width: int = 1050
    minimum_height: int = 680
    control_panel_width: int = 300
    theory_panel_width: int = 350

    capacity: int = 10
    fps: int = 60
    default_animation_ms: int = 480
    minimum_animation_ms: int = 120
    maximum_animation_ms: int = 1200

    canvas_padding: int = 48
    element_width: int = 116
    element_height: int = 48
    element_gap: int = 10
    element_corner_radius: int = 12

    font_family: str = "Segoe UI"
    monospace_font_family: str = "Consolas"
    title_font_size: int = 20
    heading_font_size: int = 12
    body_font_size: int = 10
    small_font_size: int = 9

    random_minimum: int = 1
    random_maximum: int = 999
    maximum_input_length: int = 18

    @property
    def frame_interval_ms(self) -> int:
        """Return the ideal frame interval for the configured FPS."""

        return max(1, round(1000 / self.fps))

    def animation_duration(self, speed_multiplier: float) -> int:
        """Return a bounded animation duration for a speed multiplier."""

        safe_speed = max(0.25, min(2.0, speed_multiplier))
        duration = int(self.default_animation_ms / safe_speed)
        return max(
            self.minimum_animation_ms,
            min(self.maximum_animation_ms, duration),
        )
