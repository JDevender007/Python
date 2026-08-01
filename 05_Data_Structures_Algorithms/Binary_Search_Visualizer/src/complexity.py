"""Time and space complexity information panel."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .config import FONT_BODY, FONT_SMALL, FONT_SUBTITLE, PALETTE, PANEL_PADDING

COMPLEXITY_DATA: dict[str, dict[str, str]] = {
    "Binary Search": {
        "Best Case": "O(1)",
        "Average Case": "O(log n)",
        "Worst Case": "O(log n)",
        "Space Complexity": "O(1)",
    },
    "Linear Search": {
        "Best Case": "O(1)",
        "Average Case": "O(n)",
        "Worst Case": "O(n)",
        "Space Complexity": "O(1)",
    },
}


class ComplexityPanel(ttk.Frame):
    """Display algorithm complexity values in a compact comparison table."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, style="Card.TFrame", padding=PANEL_PADDING)
        self._build()

    def _build(self) -> None:
        title = ttk.Label(
            self,
            text="Complexity Analysis",
            style="CardTitle.TLabel",
            font=FONT_SUBTITLE,
        )
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        headers = ("Metric", "Binary", "Linear")
        for column, text in enumerate(headers):
            ttk.Label(
                self,
                text=text,
                style="Muted.TLabel",
                font=FONT_SMALL,
            ).grid(row=1, column=column, sticky="w", padx=(0, 8), pady=(0, 4))

        metrics = (
            "Best Case",
            "Average Case",
            "Worst Case",
            "Space Complexity",
        )
        for row, metric in enumerate(metrics, start=2):
            ttk.Label(
                self,
                text=metric,
                style="Card.TLabel",
                font=FONT_BODY,
            ).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
            ttk.Label(
                self,
                text=COMPLEXITY_DATA["Binary Search"][metric],
                style="Accent.TLabel",
                font=FONT_BODY,
            ).grid(row=row, column=1, sticky="w", padx=(0, 8), pady=2)
            ttk.Label(
                self,
                text=COMPLEXITY_DATA["Linear Search"][metric],
                style="Accent.TLabel",
                font=FONT_BODY,
            ).grid(row=row, column=2, sticky="w", pady=2)

        self.columnconfigure(0, weight=1)
