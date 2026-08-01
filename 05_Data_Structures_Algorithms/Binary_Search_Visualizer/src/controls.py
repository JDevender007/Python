"""Control and live-statistics panels for the application."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from tkinter import ttk

from .config import (
    ALGORITHMS,
    ALGORITHM_BINARY,
    DEFAULT_ANIMATION_DELAY_MS,
    DEFAULT_ARRAY_SIZE,
    FONT_BODY,
    FONT_SMALL,
    FONT_SUBTITLE,
    MAX_ANIMATION_DELAY_MS,
    MAX_ARRAY_SIZE,
    MIN_ANIMATION_DELAY_MS,
    MIN_ARRAY_SIZE,
    PANEL_PADDING,
)


@dataclass(frozen=True, slots=True)
class ControlCallbacks:
    """Callbacks supplied by the main application controller."""

    generate: Callable[[], None]
    apply_custom_array: Callable[[], None]
    start: Callable[[], None]
    pause: Callable[[], None]
    resume: Callable[[], None]
    stop: Callable[[], None]
    reset: Callable[[], None]
    shuffle: Callable[[], None]
    algorithm_changed: Callable[[str], None]


class ControlPanel(ttk.Frame):
    """Create inputs and state-aware search controls."""

    def __init__(
        self,
        parent: tk.Misc,
        callbacks: ControlCallbacks,
    ) -> None:
        super().__init__(parent, style="Card.TFrame", padding=PANEL_PADDING)
        self.callbacks = callbacks
        self.algorithm_var = tk.StringVar(value=ALGORITHM_BINARY)
        self.array_size_var = tk.IntVar(value=DEFAULT_ARRAY_SIZE)
        self.speed_var = tk.IntVar(value=DEFAULT_ANIMATION_DELAY_MS)
        self.target_var = tk.StringVar()
        self.custom_array_var = tk.StringVar()
        self.buttons: dict[str, ttk.Button] = {}
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        ttk.Label(
            self,
            text="Controls",
            style="CardTitle.TLabel",
            font=FONT_SUBTITLE,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self._label("Algorithm", 1)
        algorithm_box = ttk.Combobox(
            self,
            textvariable=self.algorithm_var,
            values=ALGORITHMS,
            state="readonly",
            font=FONT_BODY,
        )
        algorithm_box.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        algorithm_box.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.callbacks.algorithm_changed(
                self.algorithm_var.get()
            ),
        )

        self._label("Search value", 3)
        self.target_entry = ttk.Entry(
            self,
            textvariable=self.target_var,
            font=FONT_BODY,
        )
        self.target_entry.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self._label("Custom array (comma or space separated)", 5)
        custom_entry = ttk.Entry(
            self,
            textvariable=self.custom_array_var,
            font=FONT_BODY,
        )
        custom_entry.grid(row=6, column=0, sticky="ew", padx=(0, 4), pady=(0, 8))
        apply_button = ttk.Button(
            self,
            text="Apply",
            command=self.callbacks.apply_custom_array,
            style="Secondary.TButton",
        )
        apply_button.grid(row=6, column=1, sticky="ew", padx=(4, 0), pady=(0, 8))

        self._label("Array size", 7)
        self.array_size_label = ttk.Label(
            self,
            text=str(self.array_size_var.get()),
            style="Accent.TLabel",
            font=FONT_SMALL,
        )
        self.array_size_label.grid(row=7, column=1, sticky="e")
        array_slider = ttk.Scale(
            self,
            from_=MIN_ARRAY_SIZE,
            to=MAX_ARRAY_SIZE,
            variable=self.array_size_var,
            command=self._update_array_size_label,
        )
        array_slider.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self._label("Animation speed", 9)
        self.speed_label = ttk.Label(
            self,
            text=self._speed_text(self.speed_var.get()),
            style="Accent.TLabel",
            font=FONT_SMALL,
        )
        self.speed_label.grid(row=9, column=1, sticky="e")
        speed_slider = ttk.Scale(
            self,
            from_=MAX_ANIMATION_DELAY_MS,
            to=MIN_ANIMATION_DELAY_MS,
            variable=self.speed_var,
            command=self._update_speed_label,
        )
        speed_slider.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        button_specs = (
            ("generate", "Generate", self.callbacks.generate, "Primary.TButton"),
            ("shuffle", "Shuffle", self.callbacks.shuffle, "Secondary.TButton"),
            ("start", "Start", self.callbacks.start, "Success.TButton"),
            ("pause", "Pause", self.callbacks.pause, "Secondary.TButton"),
            ("resume", "Resume", self.callbacks.resume, "Primary.TButton"),
            ("stop", "Stop", self.callbacks.stop, "Danger.TButton"),
            ("reset", "Reset", self.callbacks.reset, "Secondary.TButton"),
        )
        for index, (name, text, command, style) in enumerate(button_specs):
            row = 11 + index // 2
            column = index % 2
            button = ttk.Button(
                self,
                text=text,
                command=command,
                style=style,
            )
            button.configure(takefocus=True)
            button.grid(
                row=row,
                column=column,
                sticky="ew",
                padx=(0, 4) if column == 0 else (4, 0),
                pady=4,
            )
            self.buttons[name] = button

        self.buttons["reset"].grid(columnspan=2, sticky="ew", padx=0)

    def _label(self, text: str, row: int) -> None:
        ttk.Label(
            self,
            text=text,
            style="Card.TLabel",
            font=FONT_SMALL,
        ).grid(row=row, column=0, sticky="w", pady=(2, 3))

    def _update_array_size_label(self, raw_value: str) -> None:
        value = round(float(raw_value))
        self.array_size_var.set(value)
        self.array_size_label.configure(text=str(value))

    def _update_speed_label(self, raw_value: str) -> None:
        value = round(float(raw_value))
        self.speed_var.set(value)
        self.speed_label.configure(text=self._speed_text(value))

    @staticmethod
    def _speed_text(delay_ms: int) -> str:
        if delay_ms <= 180:
            return "Fast"
        if delay_ms <= 520:
            return "Medium"
        return "Slow"

    def set_button_states(self, states: Mapping[str, bool]) -> None:
        """Enable or disable buttons using a name-to-enabled mapping."""

        for name, enabled in states.items():
            button = self.buttons.get(name)
            if button is not None:
                button.configure(state="normal" if enabled else "disabled")

    def focus_target(self) -> None:
        """Move keyboard focus to the search target entry."""

        self.target_entry.focus_set()
        self.target_entry.selection_range(0, tk.END)


class StatisticsPanel(ttk.Frame):
    """Display live search metrics."""

    STAT_KEYS = (
        "Current Algorithm",
        "Comparisons",
        "Execution Time",
        "Current Step",
        "Array Size",
        "Search Value",
        "Status",
        "FPS Counter",
    )

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, style="Card.TFrame", padding=PANEL_PADDING)
        self.variables = {
            key: tk.StringVar(value="—") for key in self.STAT_KEYS
        }
        self._build()

    def _build(self) -> None:
        ttk.Label(
            self,
            text="Live Statistics",
            style="CardTitle.TLabel",
            font=FONT_SUBTITLE,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        for row, key in enumerate(self.STAT_KEYS, start=1):
            ttk.Label(
                self,
                text=key,
                style="Muted.TLabel",
                font=FONT_SMALL,
            ).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
            ttk.Label(
                self,
                textvariable=self.variables[key],
                style="Card.TLabel",
                font=FONT_BODY,
                anchor="e",
            ).grid(row=row, column=1, sticky="e", pady=2)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def update_stats(self, **values: object) -> None:
        """Update any statistics whose keys match display labels."""

        for key, value in values.items():
            display_key = key.replace("_", " ").title()
            variable = self.variables.get(display_key)
            if variable is not None:
                variable.set(str(value))
