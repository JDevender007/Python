"""Typed application configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WindowConfig:
    """Window geometry and behavior."""

    title: str = "Graph Traversal Visualizer"
    width: int = 1440
    height: int = 900
    min_width: int = 1050
    min_height: int = 680


@dataclass(frozen=True, slots=True)
class CanvasConfig:
    """Graph canvas dimensions and drawing settings."""

    node_radius: int = 24
    node_outline_width: int = 2
    edge_width: int = 2
    highlighted_edge_width: int = 5
    hit_padding: int = 8
    canvas_padding: int = 58


@dataclass(frozen=True, slots=True)
class AnimationConfig:
    """Animation timing configuration."""

    target_fps: int = 60
    edge_duration_seconds: float = 0.45
    visit_duration_seconds: float = 0.38
    start_duration_seconds: float = 0.18
    min_speed: float = 0.25
    max_speed: float = 3.0
    default_speed: float = 1.0


@dataclass(frozen=True, slots=True)
class LayoutConfig:
    """Spacing and component sizing."""

    padding: int = 16
    panel_padding: int = 14
    left_panel_width: int = 290
    right_panel_width: int = 300
    header_height: int = 74


@dataclass(frozen=True, slots=True)
class FontConfig:
    """Cross-platform font configuration."""

    family: str = "TkDefaultFont"
    mono_family: str = "TkFixedFont"
    title_size: int = 22
    heading_size: int = 12
    body_size: int = 10
    small_size: int = 9


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Root application configuration."""

    window: WindowConfig = field(default_factory=WindowConfig)
    canvas: CanvasConfig = field(default_factory=CanvasConfig)
    animation: AnimationConfig = field(default_factory=AnimationConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    fonts: FontConfig = field(default_factory=FontConfig)
    default_node_count: int = 10
    min_node_count: int = 2
    max_node_count: int = 30
    default_edge_weight: int = 1
