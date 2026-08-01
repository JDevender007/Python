"""Reusable control panel for simulator operations."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk

from .config import AppConfig


Action = Callable[[], None]
StructureChangeAction = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class ControlCallbacks:
    """Callbacks invoked by control-panel widgets."""

    push: Action
    pop: Action
    peek: Action
    enqueue: Action
    dequeue: Action
    front: Action
    rear: Action
    clear: Action
    reset: Action
    random_fill: Action
    structure_changed: StructureChangeAction


class ControlPanel(ttk.Frame):
    """Input controls and operation buttons for both data structures."""

    def __init__(
        self,
        master: tk.Misc,
        config: AppConfig,
        callbacks: ControlCallbacks,
    ) -> None:
        super().__init__(master, style="Panel.TFrame", padding=(18, 18))
        self._config = config
        self._callbacks = callbacks

        self._structure_var = tk.StringVar(value="Stack")
        self._element_var = tk.StringVar()
        self._speed_var = tk.DoubleVar(value=1.0)
        self._count_var = tk.IntVar(value=min(5, config.capacity))
        self._speed_label_var = tk.StringVar(value="1.00×")
        self._count_label_var = tk.StringVar(value=str(self._count_var.get()))

        self.columnconfigure(0, weight=1)
        self._build_header()
        self._build_structure_selector()
        self._build_element_input()
        self._build_operation_buttons()
        self._build_sliders()
        self._build_shortcut_hint()

    def _build_header(self) -> None:
        ttk.Label(
            self,
            text="CONTROL CENTER",
            style="Eyebrow.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text="Operations",
            style="SectionTitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 18))

    def _build_structure_selector(self) -> None:
        frame = ttk.Frame(self, style="Panel.TFrame")
        frame.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Data structure", style="Field.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 6),
        )
        selector = ttk.Combobox(
            frame,
            textvariable=self._structure_var,
            values=("Stack", "Queue"),
            state="readonly",
            style="Dark.TCombobox",
        )
        selector.grid(row=1, column=0, sticky="ew")
        selector.bind("<<ComboboxSelected>>", self._on_structure_changed)

    def _build_element_input(self) -> None:
        frame = ttk.Frame(self, style="Panel.TFrame")
        frame.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Element input", style="Field.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 6),
        )
        self.element_entry = ttk.Entry(
            frame,
            textvariable=self._element_var,
            style="Dark.TEntry",
            font=(self._config.font_family, self._config.body_font_size),
        )
        self.element_entry.grid(row=1, column=0, sticky="ew", ipady=6)
        self.element_entry.bind("<Return>", self._on_return)

    def _build_operation_buttons(self) -> None:
        frame = ttk.Frame(self, style="Panel.TFrame")
        frame.grid(row=4, column=0, sticky="ew")
        frame.columnconfigure((0, 1), weight=1, uniform="button")

        buttons: tuple[tuple[str, Action, str], ...] = (
            ("Push", self._callbacks.push, "Accent.TButton"),
            ("Pop", self._callbacks.pop, "Dark.TButton"),
            ("Peek", self._callbacks.peek, "Dark.TButton"),
            ("Enqueue", self._callbacks.enqueue, "Accent.TButton"),
            ("Dequeue", self._callbacks.dequeue, "Dark.TButton"),
            ("Front", self._callbacks.front, "Dark.TButton"),
            ("Rear", self._callbacks.rear, "Dark.TButton"),
            ("Clear", self._callbacks.clear, "Danger.TButton"),
            ("Reset", self._callbacks.reset, "Dark.TButton"),
            ("Random Fill", self._callbacks.random_fill, "Wide.TButton"),
        )

        for index, (label, command, style) in enumerate(buttons):
            if label == "Random Fill":
                row = 5
                column = 0
                column_span = 2
            else:
                row = index // 2
                column = index % 2
                column_span = 1

            ttk.Button(
                frame,
                text=label,
                command=command,
                style=style,
                cursor="hand2",
            ).grid(
                row=row,
                column=column,
                columnspan=column_span,
                sticky="ew",
                padx=(0, 5) if column == 0 and column_span == 1 else (5, 0)
                if column == 1
                else 0,
                pady=5,
                ipady=5,
            )

    def _build_sliders(self) -> None:
        frame = ttk.Frame(self, style="Panel.TFrame")
        frame.grid(row=5, column=0, sticky="ew", pady=(18, 0))
        frame.columnconfigure(0, weight=1)

        speed_header = ttk.Frame(frame, style="Panel.TFrame")
        speed_header.grid(row=0, column=0, sticky="ew")
        speed_header.columnconfigure(0, weight=1)
        ttk.Label(
            speed_header,
            text="Animation speed",
            style="Field.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            speed_header,
            textvariable=self._speed_label_var,
            style="Value.TLabel",
        ).grid(row=0, column=1, sticky="e")

        ttk.Scale(
            frame,
            from_=0.25,
            to=2.0,
            variable=self._speed_var,
            command=self._on_speed_changed,
            orient=tk.HORIZONTAL,
            style="Accent.Horizontal.TScale",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 16))

        count_header = ttk.Frame(frame, style="Panel.TFrame")
        count_header.grid(row=2, column=0, sticky="ew")
        count_header.columnconfigure(0, weight=1)
        ttk.Label(
            count_header,
            text="Random element count",
            style="Field.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            count_header,
            textvariable=self._count_label_var,
            style="Value.TLabel",
        ).grid(row=0, column=1, sticky="e")

        ttk.Scale(
            frame,
            from_=1,
            to=self._config.capacity,
            variable=self._count_var,
            command=self._on_count_changed,
            orient=tk.HORIZONTAL,
            style="Accent.Horizontal.TScale",
        ).grid(row=3, column=0, sticky="ew", pady=(6, 0))

    def _build_shortcut_hint(self) -> None:
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(
            row=6,
            column=0,
            sticky="ew",
            pady=(20, 12),
        )
        ttk.Label(
            self,
            text="P Push  •  O Pop  •  E Enqueue\n"
            "D Dequeue  •  C Clear  •  R Reset",
            style="Hint.TLabel",
            justify=tk.LEFT,
        ).grid(row=7, column=0, sticky="w")

    def _on_structure_changed(self, _event: tk.Event[tk.Misc]) -> None:
        self._callbacks.structure_changed(self._structure_var.get())

    def _on_return(self, _event: tk.Event[tk.Misc]) -> str:
        if self.selected_structure == "Stack":
            self._callbacks.push()
        else:
            self._callbacks.enqueue()
        return "break"

    def _on_speed_changed(self, raw_value: str) -> None:
        self._speed_label_var.set(f"{float(raw_value):.2f}×")

    def _on_count_changed(self, raw_value: str) -> None:
        rounded = int(round(float(raw_value)))
        self._count_var.set(rounded)
        self._count_label_var.set(str(rounded))

    @property
    def selected_structure(self) -> str:
        """Return the currently selected data structure."""

        return self._structure_var.get()

    @property
    def element_value(self) -> str:
        """Return the current element input text."""

        return self._element_var.get()

    @property
    def speed_multiplier(self) -> float:
        """Return the selected animation speed multiplier."""

        return float(self._speed_var.get())

    @property
    def random_fill_count(self) -> int:
        """Return the requested number of random elements."""

        return int(round(self._count_var.get()))

    def clear_element_input(self) -> None:
        """Clear and refocus the element input field."""

        self._element_var.set("")
        self.element_entry.focus_set()

    def select_structure(self, structure: str, notify: bool = True) -> None:
        """Select Stack or Queue and optionally notify the application."""

        normalized = structure.title()
        if normalized not in {"Stack", "Queue"}:
            raise ValueError(f"Unsupported data structure: {structure}")
        self._structure_var.set(normalized)
        if notify:
            self._callbacks.structure_changed(normalized)
