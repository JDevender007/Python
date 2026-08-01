"""Color definitions for the application's dark theme."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColorPalette:
    """Named colors used throughout the user interface."""

    background: str = "#0B1020"
    panel: str = "#11182B"
    panel_alt: str = "#172036"
    panel_hover: str = "#1D2944"
    border: str = "#273552"
    canvas: str = "#0D1425"

    text_primary: str = "#F4F7FB"
    text_secondary: str = "#AAB6CC"
    text_muted: str = "#71809B"

    accent: str = "#55D6BE"
    accent_hover: str = "#76E4CF"
    accent_dark: str = "#1F7F73"
    secondary: str = "#6EA8FE"
    highlight: str = "#FFD166"

    success: str = "#4ADE80"
    warning: str = "#FBBF24"
    danger: str = "#FB7185"
    info: str = "#60A5FA"

    stack_fill: str = "#1E766D"
    stack_outline: str = "#70E1CE"
    queue_fill: str = "#315C9C"
    queue_outline: str = "#82B6FF"
    ghost_fill: str = "#7C5CBF"


DARK_PALETTE = ColorPalette()
