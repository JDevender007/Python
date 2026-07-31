from __future__ import annotations

"""Control panel widgets for Sorting Visualizer."""

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk

from algorithms import ALGORITHMS
from src import config


class ControlPanel(ttk.Frame):
    """Own and coordinate all user input controls."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_start: Callable[[], None],
        on_pause: Callable[[], None],
        on_resume: Callable[[], None],
        on_stop: Callable[[], None],
        on_reset: Callable[[], None],
        on_shuffle: Callable[[], None],
        on_generate: Callable[[], None],
        on_size_changed: Callable[[int], None],
        on_algorithm_changed: Callable[[str], None],
    ) -> None:
        """Initialize controls and connect callbacks."""
        super().__init__(parent, style="Panel.TFrame", padding=config.PANEL_PADDING)
        self._on_size_changed = on_size_changed
        self._on_algorithm_changed = on_algorithm_changed

        self.algorithm_var = tk.StringVar(value=next(iter(ALGORITHMS)))
        self.size_var = tk.IntVar(value=config.DEFAULT_ARRAY_SIZE)
        self.speed_var = tk.DoubleVar(value=config.DEFAULT_SPEED)
        self.size_display_var = tk.StringVar(value=str(config.DEFAULT_ARRAY_SIZE))
        self.speed_display_var = tk.StringVar(value=f"{config.DEFAULT_SPEED} steps/s")
        self.buttons: dict[str, ttk.Button] = {}

        self._build_algorithm_controls()
        self._build_sliders()
        self._build_buttons(
            on_start=on_start,
            on_pause=on_pause,
            on_resume=on_resume,
            on_stop=on_stop,
            on_reset=on_reset,
            on_shuffle=on_shuffle,
            on_generate=on_generate,
        )
        self.set_application_state("Ready")

    def _build_algorithm_controls(self) -> None:
        ttk.Label(self, text="Algorithm", style="Heading.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.algorithm_combo = ttk.Combobox(
            self,
            textvariable=self.algorithm_var,
            values=tuple(ALGORITHMS.keys()),
            state="readonly",
            width=20,
        )
        self.algorithm_combo.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 12))
        self.algorithm_combo.bind("<<ComboboxSelected>>", self._algorithm_selected)

    def _build_sliders(self) -> None:
        ttk.Label(self, text="Array size", style="Heading.TLabel").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(self, textvariable=self.size_display_var, style="Value.TLabel").grid(
            row=2, column=1, sticky="e"
        )
        self.size_scale = ttk.Scale(
            self,
            from_=config.MIN_ARRAY_SIZE,
            to=config.MAX_ARRAY_SIZE,
            variable=self.size_var,
            command=self._size_dragged,
        )
        self.size_scale.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5, 12))
        self.size_scale.bind("<ButtonRelease-1>", self._size_released)

        ttk.Label(self, text="Animation speed", style="Heading.TLabel").grid(
            row=4, column=0, sticky="w"
        )
        ttk.Label(self, textvariable=self.speed_display_var, style="Value.TLabel").grid(
            row=4, column=1, sticky="e"
        )
        self.speed_scale = ttk.Scale(
            self,
            from_=config.MIN_SPEED,
            to=config.MAX_SPEED,
            variable=self.speed_var,
            command=self._speed_dragged,
        )
        self.speed_scale.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(5, 14))

    def _build_buttons(
        self,
        *,
        on_start: Callable[[], None],
        on_pause: Callable[[], None],
        on_resume: Callable[[], None],
        on_stop: Callable[[], None],
        on_reset: Callable[[], None],
        on_shuffle: Callable[[], None],
        on_generate: Callable[[], None],
    ) -> None:
        button_specs = (
            ("start", "Start", on_start, "Accent.TButton"),
            ("pause", "Pause", on_pause, "TButton"),
            ("resume", "Resume", on_resume, "TButton"),
            ("stop", "Stop", on_stop, "Danger.TButton"),
            ("reset", "Reset", on_reset, "TButton"),
            ("shuffle", "Shuffle", on_shuffle, "TButton"),
            ("generate", "Generate", on_generate, "TButton"),
        )

        for row_offset, (key, text, callback, style) in enumerate(button_specs, start=6):
            button = ttk.Button(self, text=text, command=callback, style=style)
            button.grid(row=row_offset, column=0, columnspan=2, sticky="ew", pady=3)
            self.buttons[key] = button

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def _size_dragged(self, raw_value: str) -> None:
        size = round(float(raw_value))
        self.size_var.set(size)
        self.size_display_var.set(str(size))

    def _size_released(self, _event: tk.Event[tk.Misc]) -> None:
        self._on_size_changed(self.get_array_size())

    def _speed_dragged(self, raw_value: str) -> None:
        speed = round(float(raw_value))
        self.speed_var.set(speed)
        self.speed_display_var.set(f"{speed} steps/s")

    def _algorithm_selected(self, _event: tk.Event[tk.Misc]) -> None:
        self._on_algorithm_changed(self.get_algorithm())

    def get_algorithm(self) -> str:
        """Return the selected algorithm name."""
        return self.algorithm_var.get()

    def get_array_size(self) -> int:
        """Return the selected array size."""
        return int(round(self.size_var.get()))

    def get_speed(self) -> float:
        """Return desired generator steps per second."""
        return float(self.speed_var.get())

    def set_application_state(self, state: str) -> None:
        """Enable and disable controls for the current application state."""
        enabled_by_state: dict[str, set[str]] = {
            "Ready": {"start", "reset", "shuffle", "generate"},
            "Running": {"pause", "stop"},
            "Paused": {"resume", "stop", "reset"},
            "Stopped": {"start", "reset", "shuffle", "generate"},
            "Finished": {"reset", "shuffle", "generate"},
        }
        enabled = enabled_by_state.get(state, set())

        for key, button in self.buttons.items():
            button.configure(state="normal" if key in enabled else "disabled")

        lock_settings = state in {"Running", "Paused"}
        self.algorithm_combo.configure(state="disabled" if lock_settings else "readonly")
        self.size_scale.configure(state="disabled" if lock_settings else "normal")
