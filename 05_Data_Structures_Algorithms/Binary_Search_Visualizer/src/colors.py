"""Color definitions for the Binary Search Visualizer dark theme."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColorPalette:
    """Immutable application color palette."""

    background: str = "#0B1020"
    surface: str = "#121A2E"
    surface_alt: str = "#18233B"
    border: str = "#2A3857"
    default_bar: str = "#4F78D1"
    current_element: str = "#F6C85F"
    left_boundary: str = "#33C3F0"
    right_boundary: str = "#A66CFF"
    middle_element: str = "#FF9F43"
    found_element: str = "#2ED573"
    not_found: str = "#FF4757"
    text: str = "#F5F7FF"
    muted_text: str = "#A9B5D0"
    grid: str = "#263554"
    accent: str = "#6C8CFF"
    accent_hover: str = "#86A0FF"
    disabled: str = "#46516A"
    input_background: str = "#0F172A"
    selection: str = "#3558B8"
