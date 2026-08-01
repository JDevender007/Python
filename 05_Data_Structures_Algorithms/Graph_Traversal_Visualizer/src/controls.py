"""Control panel widgets for the graph visualizer."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk

from src.colors import Colors
from src.config import AppConfig
from src.graph_canvas import EditorMode


@dataclass(frozen=True, slots=True)
class ControlCallbacks:
    """Commands supplied to :class:`ControlPanel`."""

    generate_graph: Callable[[], None]
    start_traversal: Callable[[], None]
    pause_traversal: Callable[[], None]
    resume_traversal: Callable[[], None]
    stop_traversal: Callable[[], None]
    reset_visualization: Callable[[], None]
    clear_graph: Callable[[], None]
    algorithm_changed: Callable[[str], None]
    editor_mode_changed: Callable[[EditorMode], None]


class ControlPanel(tk.Frame):
    """Algorithm, animation, graph, and editor controls."""

    def __init__(
        self,
        parent: tk.Misc,
        config: AppConfig,
        callbacks: ControlCallbacks,
    ) -> None:
        super().__init__(parent, bg=Colors.BACKGROUND)
        self._config = config
        self._callbacks = callbacks
        self._algorithm_var = tk.StringVar(value="BFS")
        self._node_count_var = tk.IntVar(value=config.default_node_count)
        self._speed_var = tk.DoubleVar(value=config.animation.default_speed)
        self._weight_var = tk.IntVar(value=config.default_edge_weight)
        self._node_count_text = tk.StringVar(value=str(config.default_node_count))
        self._speed_text = tk.StringVar(value="1.00×")
        self._mode_buttons: dict[EditorMode, tk.Button] = {}
        self._action_buttons: dict[str, tk.Button] = {}
        self._active_mode = EditorMode.MOVE_NODE
        self._build()
        self.set_editor_mode(self._active_mode)
        self.set_animation_state("idle")

    @property
    def algorithm(self) -> str:
        """Return the selected traversal algorithm."""
        return self._algorithm_var.get().upper()

    @property
    def node_count(self) -> int:
        """Return the requested random graph size."""
        return int(self._node_count_var.get())

    @property
    def animation_speed(self) -> float:
        """Return the selected animation speed multiplier."""
        return float(self._speed_var.get())

    @property
    def edge_weight(self) -> float:
        """Return the weight used when manually creating edges."""
        return float(self._weight_var.get())

    def _build(self) -> None:
        self._build_algorithm_section()
        self._build_graph_section()
        self._build_animation_section()
        self._build_editor_section()
        self._build_help_section()

    def _section(self, title: str) -> tk.Frame:
        frame = tk.Frame(
            self,
            bg=Colors.SURFACE,
            highlightbackground=Colors.BORDER,
            highlightthickness=1,
        )
        frame.pack(fill="x", pady=(0, 12))
        tk.Label(
            frame,
            text=title,
            bg=Colors.SURFACE,
            fg=Colors.TEXT_MUTED,
            font=(self._config.fonts.family, 9, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 8))
        return frame

    def _build_algorithm_section(self) -> None:
        frame = self._section("TRAVERSAL")
        content = tk.Frame(frame, bg=Colors.SURFACE)
        content.pack(fill="x", padx=14, pady=(0, 14))

        tk.Label(
            content,
            text="Algorithm",
            bg=Colors.SURFACE,
            fg=Colors.TEXT,
            font=(self._config.fonts.family, 10),
        ).pack(anchor="w", pady=(0, 5))

        combo = ttk.Combobox(
            content,
            textvariable=self._algorithm_var,
            values=("BFS", "DFS"),
            state="readonly",
            font=(self._config.fonts.family, 10),
        )
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", self._on_algorithm_changed)

        self._action_buttons["start"] = self._button(
            content,
            "▶  Start Traversal",
            self._callbacks.start_traversal,
            primary=True,
        )
        self._action_buttons["start"].pack(fill="x", pady=(10, 0))

    def _build_graph_section(self) -> None:
        frame = self._section("GRAPH")
        content = tk.Frame(frame, bg=Colors.SURFACE)
        content.pack(fill="x", padx=14, pady=(0, 14))

        top = tk.Frame(content, bg=Colors.SURFACE)
        top.pack(fill="x")
        tk.Label(
            top,
            text="Node Count",
            bg=Colors.SURFACE,
            fg=Colors.TEXT,
            font=(self._config.fonts.family, 10),
        ).pack(side="left")
        tk.Label(
            top,
            textvariable=self._node_count_text,
            bg=Colors.SURFACE,
            fg=Colors.SECONDARY,
            font=(self._config.fonts.mono_family, 10, "bold"),
        ).pack(side="right")

        node_scale = tk.Scale(
            content,
            from_=self._config.min_node_count,
            to=self._config.max_node_count,
            orient="horizontal",
            variable=self._node_count_var,
            command=self._on_node_count_changed,
            resolution=1,
            showvalue=False,
            bg=Colors.SURFACE,
            fg=Colors.TEXT,
            troughcolor=Colors.SURFACE_ALT,
            activebackground=Colors.PRIMARY,
            highlightthickness=0,
            bd=0,
            sliderlength=18,
        )
        node_scale.pack(fill="x", pady=(4, 8))

        self._action_buttons["generate"] = self._button(
            content,
            "⟳  Generate Graph",
            self._callbacks.generate_graph,
        )
        self._action_buttons["generate"].pack(fill="x")

        button_row = tk.Frame(content, bg=Colors.SURFACE)
        button_row.pack(fill="x", pady=(8, 0))
        self._action_buttons["reset"] = self._button(
            button_row,
            "Reset Graph",
            self._callbacks.reset_visualization,
        )
        self._action_buttons["reset"].pack(side="left", fill="x", expand=True)
        self._action_buttons["clear"] = self._button(
            button_row,
            "Clear",
            self._callbacks.clear_graph,
            danger=True,
        )
        self._action_buttons["clear"].pack(
            side="left", fill="x", expand=True, padx=(8, 0)
        )

    def _build_animation_section(self) -> None:
        frame = self._section("ANIMATION")
        content = tk.Frame(frame, bg=Colors.SURFACE)
        content.pack(fill="x", padx=14, pady=(0, 14))

        top = tk.Frame(content, bg=Colors.SURFACE)
        top.pack(fill="x")
        tk.Label(
            top,
            text="Speed",
            bg=Colors.SURFACE,
            fg=Colors.TEXT,
            font=(self._config.fonts.family, 10),
        ).pack(side="left")
        tk.Label(
            top,
            textvariable=self._speed_text,
            bg=Colors.SURFACE,
            fg=Colors.ACCENT,
            font=(self._config.fonts.mono_family, 10, "bold"),
        ).pack(side="right")

        speed_scale = tk.Scale(
            content,
            from_=self._config.animation.min_speed,
            to=self._config.animation.max_speed,
            orient="horizontal",
            variable=self._speed_var,
            command=self._on_speed_changed,
            resolution=0.05,
            showvalue=False,
            bg=Colors.SURFACE,
            fg=Colors.TEXT,
            troughcolor=Colors.SURFACE_ALT,
            activebackground=Colors.ACCENT,
            highlightthickness=0,
            bd=0,
            sliderlength=18,
        )
        speed_scale.pack(fill="x", pady=(4, 8))

        row = tk.Frame(content, bg=Colors.SURFACE)
        row.pack(fill="x")
        self._action_buttons["pause"] = self._button(
            row, "Pause", self._callbacks.pause_traversal
        )
        self._action_buttons["pause"].pack(side="left", fill="x", expand=True)
        self._action_buttons["resume"] = self._button(
            row, "Resume", self._callbacks.resume_traversal
        )
        self._action_buttons["resume"].pack(
            side="left", fill="x", expand=True, padx=6
        )
        self._action_buttons["stop"] = self._button(
            row, "Stop", self._callbacks.stop_traversal, danger=True
        )
        self._action_buttons["stop"].pack(side="left", fill="x", expand=True)

    def _build_editor_section(self) -> None:
        frame = self._section("GRAPH EDITOR")
        content = tk.Frame(frame, bg=Colors.SURFACE)
        content.pack(fill="x", padx=14, pady=(0, 10))

        modes = (
            (EditorMode.MOVE_NODE, "Move"),
            (EditorMode.ADD_NODE, "Add Node"),
            (EditorMode.ADD_EDGE, "Add Edge"),
            (EditorMode.DELETE_NODE, "Delete Node"),
            (EditorMode.DELETE_EDGE, "Delete Edge"),
            (EditorMode.SET_START, "Set Start"),
        )
        for index, (mode, caption) in enumerate(modes):
            button = self._button(
                content,
                caption,
                lambda selected=mode: self._select_mode(selected),
                compact=True,
            )
            button.grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=(0, 4) if index % 2 == 0 else (4, 0),
                pady=(0, 8),
            )
            self._mode_buttons[mode] = button
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)

        weight_row = tk.Frame(frame, bg=Colors.SURFACE)
        weight_row.pack(fill="x", padx=14, pady=(0, 14))
        tk.Label(
            weight_row,
            text="New edge weight",
            bg=Colors.SURFACE,
            fg=Colors.TEXT_MUTED,
            font=(self._config.fonts.family, 9),
        ).pack(side="left")
        spinbox = tk.Spinbox(
            weight_row,
            from_=1,
            to=99,
            textvariable=self._weight_var,
            width=5,
            justify="center",
            bg=Colors.SURFACE_ALT,
            fg=Colors.TEXT,
            insertbackground=Colors.TEXT,
            buttonbackground=Colors.SURFACE_HOVER,
            relief="flat",
            highlightbackground=Colors.BORDER,
            highlightthickness=1,
            font=(self._config.fonts.mono_family, 9),
        )
        spinbox.pack(side="right")

    def _build_help_section(self) -> None:
        frame = self._section("CANVAS TIPS")
        tk.Label(
            frame,
            text=(
                "Double-click a node to set the start.\n"
                "Right-click nodes for quick actions.\n"
                "Use Move mode to drag vertices."
            ),
            justify="left",
            bg=Colors.SURFACE,
            fg=Colors.TEXT_MUTED,
            font=(self._config.fonts.family, 9),
        ).pack(anchor="w", padx=14, pady=(0, 14))

    def _button(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        *,
        primary: bool = False,
        danger: bool = False,
        compact: bool = False,
    ) -> tk.Button:
        background = Colors.PRIMARY if primary else Colors.SURFACE_ALT
        active_background = (
            Colors.PRIMARY_HOVER if primary else Colors.SURFACE_HOVER
        )
        foreground = Colors.WHITE if primary else Colors.TEXT
        if danger:
            foreground = Colors.DANGER
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground=active_background,
            activeforeground=Colors.WHITE,
            disabledforeground=Colors.TEXT_MUTED,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=8,
            pady=6 if compact else 8,
            font=(self._config.fonts.family, 9 if compact else 10, "bold"),
        )

    def _on_algorithm_changed(self, _event: tk.Event[tk.Misc]) -> None:
        self._callbacks.algorithm_changed(self.algorithm)

    def _on_node_count_changed(self, value: str) -> None:
        self._node_count_text.set(str(int(float(value))))

    def _on_speed_changed(self, value: str) -> None:
        self._speed_text.set(f"{float(value):.2f}×")

    def _select_mode(self, mode: EditorMode) -> None:
        self.set_editor_mode(mode)
        self._callbacks.editor_mode_changed(mode)

    def set_editor_mode(self, mode: EditorMode) -> None:
        """Visually mark the active graph editor mode."""
        self._active_mode = mode
        for candidate, button in self._mode_buttons.items():
            active = candidate is mode
            button.configure(
                bg=Colors.PRIMARY if active else Colors.SURFACE_ALT,
                fg=Colors.WHITE if active else Colors.TEXT,
                activebackground=(
                    Colors.PRIMARY_HOVER if active else Colors.SURFACE_HOVER
                ),
            )

    def set_animation_state(self, state: str) -> None:
        """Enable action buttons appropriate for an animation state."""
        normalized = state.lower()
        is_running = normalized == "running"
        is_paused = normalized == "paused"
        self._action_buttons["start"].configure(
            state="disabled" if is_running or is_paused else "normal"
        )
        self._action_buttons["pause"].configure(
            state="normal" if is_running else "disabled"
        )
        self._action_buttons["resume"].configure(
            state="normal" if is_paused else "disabled"
        )
        self._action_buttons["stop"].configure(
            state="normal" if is_running or is_paused else "disabled"
        )
