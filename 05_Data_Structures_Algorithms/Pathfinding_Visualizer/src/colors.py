"""Centralized color palette for the dark user interface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Palette:
    """Application color palette."""

    background: str = "#0B1220"
    panel: str = "#111A2B"
    panel_alt: str = "#172338"
    canvas: str = "#0E1726"
    grid_line: str = "#26354B"
    text: str = "#E8EEF8"
    muted_text: str = "#94A3B8"
    accent: str = "#38BDF8"
    accent_hover: str = "#0EA5E9"
    success: str = "#22C55E"
    warning: str = "#F59E0B"
    danger: str = "#EF4444"
    wall: str = "#334155"
    start: str = "#22C55E"
    end: str = "#F43F5E"
    visited: str = "#1D4ED8"
    visited_glow: str = "#2563EB"
    path: str = "#FACC15"
    empty: str = "#0E1726"
    border: str = "#253247"


COLORS = Palette()
