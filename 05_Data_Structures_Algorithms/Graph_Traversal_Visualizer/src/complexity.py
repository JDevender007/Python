"""Traversal complexity metadata and panel widget."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass

from src.colors import Colors
from src.config import AppConfig


@dataclass(frozen=True, slots=True)
class ComplexityInfo:
    """Complexity values displayed for one algorithm."""

    best_case: str
    average_case: str
    worst_case: str
    space: str


COMPLEXITY: dict[str, ComplexityInfo] = {
    "BFS": ComplexityInfo("O(V + E)", "O(V + E)", "O(V + E)", "O(V)"),
    "DFS": ComplexityInfo("O(V + E)", "O(V + E)", "O(V + E)", "O(V)"),
}


class ComplexityPanel(tk.Frame):
    """Dark-themed complexity summary panel."""

    def __init__(self, parent: tk.Misc, config: AppConfig) -> None:
        super().__init__(
            parent,
            bg=Colors.SURFACE,
            highlightbackground=Colors.BORDER,
            highlightthickness=1,
        )
        self._config = config
        self._value_labels: dict[str, tk.Label] = {}
        self._build()
        self.set_algorithm("BFS")

    def _build(self) -> None:
        padding = self._config.layout.panel_padding
        tk.Label(
            self,
            text="COMPLEXITY",
            bg=Colors.SURFACE,
            fg=Colors.TEXT_MUTED,
            font=(self._config.fonts.family, 9, "bold"),
        ).pack(anchor="w", padx=padding, pady=(padding, 8))

        content = tk.Frame(self, bg=Colors.SURFACE)
        content.pack(fill="x", padx=padding, pady=(0, padding))
        rows = (
            ("Best Case", "best_case"),
            ("Average Case", "average_case"),
            ("Worst Case", "worst_case"),
            ("Space", "space"),
        )
        for row_index, (caption, key) in enumerate(rows):
            tk.Label(
                content,
                text=caption,
                bg=Colors.SURFACE,
                fg=Colors.TEXT_MUTED,
                font=(self._config.fonts.family, 9),
            ).grid(row=row_index, column=0, sticky="w", pady=4)
            value_label = tk.Label(
                content,
                text="—",
                bg=Colors.SURFACE,
                fg=Colors.SECONDARY,
                font=(self._config.fonts.mono_family, 10, "bold"),
            )
            value_label.grid(row=row_index, column=1, sticky="e", pady=4)
            self._value_labels[key] = value_label
        content.grid_columnconfigure(1, weight=1)

    def set_algorithm(self, algorithm: str) -> None:
        """Update the panel for BFS or DFS."""
        info = COMPLEXITY.get(algorithm.upper(), COMPLEXITY["BFS"])
        self._value_labels["best_case"].configure(text=info.best_case)
        self._value_labels["average_case"].configure(text=info.average_case)
        self._value_labels["worst_case"].configure(text=info.worst_case)
        self._value_labels["space"].configure(text=info.space)
