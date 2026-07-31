from __future__ import annotations

"""Visualization surface and information panels."""

import tkinter as tk
from tkinter import ttk

from src import config
from src.colors import Palette
from src.complexity import get_complexity


class VisualizerFrame(ttk.Frame):
    """Render bars, metrics, complexity details, progress, and status."""

    def __init__(self, parent: tk.Misc) -> None:
        """Create the responsive visualization layout."""
        super().__init__(parent, style="App.TFrame")
        self._values: list[int] = []
        self._colors: list[str] = []
        self._bar_items: list[int] = []
        self._value_items: list[int] = []
        self._resize_job: str | None = None

        self._build_layout()
        self._build_statistics_panel()
        self._build_complexity_panel()
        self._build_status_bar()

    def _build_layout(self) -> None:
        self.canvas = tk.Canvas(
            self,
            background=Palette.CANVAS,
            highlightthickness=1,
            highlightbackground=Palette.BORDER,
            relief="flat",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(0, config.CONTENT_PADDING))
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        self.sidebar = ttk.Frame(self, style="Panel.TFrame", padding=config.PANEL_PADDING)
        self.sidebar.grid(row=0, column=1, sticky="nsew")

        self.columnconfigure(0, weight=5)
        self.columnconfigure(1, weight=0, minsize=250)
        self.rowconfigure(0, weight=1)

    def _build_statistics_panel(self) -> None:
        ttk.Label(self.sidebar, text="Statistics", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        self._stat_vars = {
            "Comparisons": tk.StringVar(value="0"),
            "Swaps": tk.StringVar(value="0"),
            "Execution Time": tk.StringVar(value="0.000 s"),
            "Current Algorithm": tk.StringVar(value="Bubble Sort"),
            "Number of Elements": tk.StringVar(value="0"),
            "FPS": tk.StringVar(value="0.0"),
        }
        row = 1
        for label, variable in self._stat_vars.items():
            ttk.Label(self.sidebar, text=label, style="Muted.TLabel").grid(
                row=row, column=0, sticky="w", pady=3
            )
            ttk.Label(
                self.sidebar,
                textvariable=variable,
                style="Metric.TLabel",
                anchor="e",
                width=16,
            ).grid(row=row, column=1, sticky="e", pady=3)
            row += 1

        ttk.Separator(self.sidebar, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=14
        )
        self._complexity_start_row = row + 1

    def _build_complexity_panel(self) -> None:
        row = self._complexity_start_row
        ttk.Label(self.sidebar, text="Complexity", style="Section.TLabel").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        row += 1
        self._complexity_vars = {
            "Best Case": tk.StringVar(),
            "Average Case": tk.StringVar(),
            "Worst Case": tk.StringVar(),
            "Space Complexity": tk.StringVar(),
        }
        for label, variable in self._complexity_vars.items():
            ttk.Label(self.sidebar, text=label, style="Muted.TLabel").grid(
                row=row, column=0, sticky="w", pady=3
            )
            ttk.Label(
                self.sidebar,
                textvariable=variable,
                style="Metric.TLabel",
                anchor="e",
            ).grid(row=row, column=1, sticky="e", pady=3)
            row += 1

        self.sidebar.columnconfigure(0, weight=1)
        self.sidebar.columnconfigure(1, weight=1)

    def _build_status_bar(self) -> None:
        status_frame = ttk.Frame(self, style="Panel.TFrame", padding=(10, 7))
        status_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self.status_var = tk.StringVar(value="Ready")
        self.status_detail_var = tk.StringVar(value="Generate an array or start sorting.")
        ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            status_frame,
            textvariable=self.status_detail_var,
            style="Muted.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))

        self.progress = ttk.Progressbar(
            status_frame,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            value=0,
        )
        self.progress.grid(row=0, column=2, sticky="ew", padx=(14, 0))
        status_frame.columnconfigure(1, weight=1)
        status_frame.columnconfigure(2, weight=2)

    def draw(self, values: list[int], colors: list[str]) -> None:
        """Draw or update the bar chart efficiently on the Tk canvas."""
        self._values = values.copy()
        self._colors = colors.copy()
        self._render_grid()
        self._render_bars()

    def _render_grid(self) -> None:
        self.canvas.delete("grid")
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        usable_height = max(
            1,
            height - config.CANVAS_PADDING_TOP - config.CANVAS_PADDING_BOTTOM,
        )

        for index in range(config.GRID_LINE_COUNT + 1):
            fraction = index / config.GRID_LINE_COUNT
            y = config.CANVAS_PADDING_TOP + usable_height * fraction
            self.canvas.create_line(
                config.CANVAS_PADDING_X,
                y,
                width - config.CANVAS_PADDING_X,
                y,
                fill=Palette.GRID,
                width=1,
                tags="grid",
            )
        self.canvas.tag_lower("grid")

    def _render_bars(self) -> None:
        if not self._values:
            self.canvas.delete("bar")
            self.canvas.delete("value")
            self._bar_items.clear()
            self._value_items.clear()
            return

        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        usable_width = max(1, width - 2 * config.CANVAS_PADDING_X)
        usable_height = max(
            1,
            height - config.CANVAS_PADDING_TOP - config.CANVAS_PADDING_BOTTOM,
        )
        count = len(self._values)
        slot_width = usable_width / count
        gap = min(config.BAR_GAP, slot_width * 0.25)
        max_value = max(self._values, default=1)
        baseline = height - config.CANVAS_PADDING_BOTTOM
        show_labels = count <= config.VALUE_LABEL_LIMIT and slot_width >= 20

        self._ensure_item_count(count, show_labels)

        for index, value in enumerate(self._values):
            x1 = config.CANVAS_PADDING_X + index * slot_width + gap / 2
            x2 = config.CANVAS_PADDING_X + (index + 1) * slot_width - gap / 2
            bar_height = (value / max_value) * usable_height
            y1 = baseline - bar_height
            color = self._colors[index] if index < len(self._colors) else Palette.BAR
            self.canvas.coords(self._bar_items[index], x1, y1, x2, baseline)
            self.canvas.itemconfigure(self._bar_items[index], fill=color, state="normal")

            if show_labels:
                self.canvas.coords(self._value_items[index], (x1 + x2) / 2, max(10, y1 - 9))
                self.canvas.itemconfigure(
                    self._value_items[index],
                    text=str(value),
                    state="normal",
                )

        for index in range(count, len(self._bar_items)):
            self.canvas.itemconfigure(self._bar_items[index], state="hidden")
        for index in range(count if show_labels else 0, len(self._value_items)):
            self.canvas.itemconfigure(self._value_items[index], state="hidden")

    def _ensure_item_count(self, count: int, show_labels: bool) -> None:
        while len(self._bar_items) < count:
            item = self.canvas.create_rectangle(
                0,
                0,
                0,
                0,
                fill=Palette.BAR,
                outline="",
                tags="bar",
            )
            self._bar_items.append(item)

        if show_labels:
            while len(self._value_items) < count:
                item = self.canvas.create_text(
                    0,
                    0,
                    fill=Palette.TEXT,
                    font=config.FONT_SMALL,
                    tags="value",
                )
                self._value_items.append(item)

    def _on_canvas_resize(self, _event: tk.Event[tk.Misc]) -> None:
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(25, self._redraw_after_resize)

    def _redraw_after_resize(self) -> None:
        self._resize_job = None
        self.draw(self._values, self._colors)

    def update_statistics(
        self,
        *,
        comparisons: int,
        swaps: int,
        execution_time: float,
        algorithm: str,
        element_count: int,
        fps: float,
    ) -> None:
        """Update the statistics panel."""
        self._stat_vars["Comparisons"].set(f"{comparisons:,}")
        self._stat_vars["Swaps"].set(f"{swaps:,}")
        self._stat_vars["Execution Time"].set(f"{execution_time:.3f} s")
        self._stat_vars["Current Algorithm"].set(algorithm)
        self._stat_vars["Number of Elements"].set(str(element_count))
        self._stat_vars["FPS"].set(f"{fps:.1f}")

    def update_complexity(self, algorithm: str) -> None:
        """Show complexity information for the selected algorithm."""
        info = get_complexity(algorithm)
        self._complexity_vars["Best Case"].set(info.best)
        self._complexity_vars["Average Case"].set(info.average)
        self._complexity_vars["Worst Case"].set(info.worst)
        self._complexity_vars["Space Complexity"].set(info.space)

    def set_status(self, status: str, detail: str = "") -> None:
        """Update the status bar text."""
        self.status_var.set(status)
        self.status_detail_var.set(detail)

    def start_progress(self) -> None:
        """Start an indeterminate progress animation."""
        self.progress.stop()
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)

    def set_progress(self, percent: float) -> None:
        """Set determinate progress to a value from zero to one hundred."""
        self.progress.stop()
        self.progress.configure(mode="determinate", value=max(0.0, min(100.0, percent)))

    def stop_progress(self, percent: float = 0.0) -> None:
        """Stop progress animation and set a final value."""
        self.progress.stop()
        self.progress.configure(mode="determinate", value=percent)
