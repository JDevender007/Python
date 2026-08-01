"""Scrollable control, statistics, and complexity panel."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from algorithms import ALGORITHMS
from src.colors import COLORS
from src.complexity import get_complexity
from src.config import AppConfig


class ControlPanel(tk.Frame):
    """Application controls and live status display."""

    def __init__(
        self,
        master: tk.Misc,
        config: AppConfig,
        on_start: Callable[[], None],
        on_pause: Callable[[], None],
        on_resume: Callable[[], None],
        on_stop: Callable[[], None],
        on_clear_path: Callable[[], None],
        on_clear_grid: Callable[[], None],
        on_reset: Callable[[], None],
        on_maze: Callable[[], None],
        on_grid_size: Callable[[int], None],
    ) -> None:
        super().__init__(
            master,
            background=COLORS.panel,
            width=config.control_panel_width,
        )
        self.pack_propagate(False)
        self._config = config
        self._on_grid_size = on_grid_size

        self.algorithm_var = tk.StringVar(value="A* Search")
        self.grid_columns_var = tk.IntVar(value=config.default_columns)
        default_speed = self._speed_value_for_delay(config.default_animation_delay_ms)
        self.speed_var = tk.IntVar(value=default_speed)
        self.grid_size_text = tk.StringVar()
        self.speed_text = tk.StringVar()

        self._stat_vars = {
            "algorithm": tk.StringVar(value="A* Search"),
            "visited": tk.StringVar(value="0"),
            "path": tk.StringVar(value="0"),
            "time": tk.StringVar(value="0.00 ms"),
            "grid": tk.StringVar(value="—"),
            "status": tk.StringVar(value="Ready"),
            "fps": tk.StringVar(value="0.0"),
        }
        self._complexity_vars = {
            "best": tk.StringVar(),
            "average": tk.StringVar(),
            "worst": tk.StringVar(),
            "space": tk.StringVar(),
            "note": tk.StringVar(),
        }

        self._configure_styles()
        self._build_scroll_area()
        self._build_header()
        self._build_algorithm_section()
        self._build_action_section(
            on_start,
            on_pause,
            on_resume,
            on_stop,
            on_clear_path,
            on_clear_grid,
            on_reset,
            on_maze,
        )
        self._build_tuning_section()
        self._build_statistics_section()
        self._build_complexity_section()
        self._build_legend()
        self._build_footer()

        self.algorithm_var.trace_add("write", self._on_algorithm_selected)
        self._refresh_slider_text()
        self.refresh_complexity()
        self.update_idletasks()
        self._sync_scroll_region()

    @property
    def selected_algorithm(self) -> str:
        """Return the currently selected algorithm name."""
        return self.algorithm_var.get()

    @property
    def selected_columns(self) -> int:
        """Return the requested grid column count."""
        return int(self.grid_columns_var.get())

    @property
    def animation_delay_ms(self) -> int:
        """Translate the speed slider into a frame delay."""
        speed = max(1, min(100, int(self.speed_var.get())))
        span = self._config.max_animation_delay_ms - self._config.min_animation_delay_ms
        normalized = (speed - 1) / 99.0
        return round(self._config.max_animation_delay_ms - normalized * span)

    def update_statistics(
        self,
        *,
        algorithm: str | None = None,
        visited: int | None = None,
        path_length: int | None = None,
        execution_time: str | None = None,
        grid_size: str | None = None,
        status: str | None = None,
        fps: float | None = None,
    ) -> None:
        """Update one or more live-statistics values."""
        if algorithm is not None:
            self._stat_vars["algorithm"].set(algorithm)
        if visited is not None:
            self._stat_vars["visited"].set(str(visited))
        if path_length is not None:
            self._stat_vars["path"].set(str(path_length))
        if execution_time is not None:
            self._stat_vars["time"].set(execution_time)
        if grid_size is not None:
            self._stat_vars["grid"].set(grid_size)
        if status is not None:
            self._stat_vars["status"].set(status)
        if fps is not None:
            self._stat_vars["fps"].set(f"{fps:.1f}")

    def refresh_complexity(self) -> None:
        """Refresh complexity labels for the selected algorithm."""
        info = get_complexity(self.selected_algorithm)
        self._complexity_vars["best"].set(info.best_case)
        self._complexity_vars["average"].set(info.average_case)
        self._complexity_vars["worst"].set(info.worst_case)
        self._complexity_vars["space"].set(info.space)
        self._complexity_vars["note"].set(info.note)

    def set_animation_state(self, state: str) -> None:
        """Set button availability for ready, running, or paused states."""
        if state == "running":
            self.start_button.configure(state=tk.DISABLED)
            self.pause_button.configure(state=tk.NORMAL)
            self.resume_button.configure(state=tk.DISABLED)
            self.stop_button.configure(state=tk.NORMAL)
        elif state == "paused":
            self.start_button.configure(state=tk.DISABLED)
            self.pause_button.configure(state=tk.DISABLED)
            self.resume_button.configure(state=tk.NORMAL)
            self.stop_button.configure(state=tk.NORMAL)
        else:
            self.start_button.configure(state=tk.NORMAL)
            self.pause_button.configure(state=tk.DISABLED)
            self.resume_button.configure(state=tk.DISABLED)
            self.stop_button.configure(state=tk.DISABLED)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Dark.TCombobox",
            fieldbackground=COLORS.panel_alt,
            background=COLORS.panel_alt,
            foreground=COLORS.text,
            arrowcolor=COLORS.text,
            bordercolor=COLORS.border,
            lightcolor=COLORS.border,
            darkcolor=COLORS.border,
            padding=8,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", COLORS.panel_alt)],
            foreground=[("readonly", COLORS.text)],
            selectbackground=[("readonly", COLORS.panel_alt)],
            selectforeground=[("readonly", COLORS.text)],
        )

    def _build_scroll_area(self) -> None:
        self._scroll_canvas = tk.Canvas(
            self,
            background=COLORS.panel,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = tk.Scrollbar(
            self,
            orient=tk.VERTICAL,
            command=self._scroll_canvas.yview,
            background=COLORS.panel_alt,
            troughcolor=COLORS.panel,
            activebackground=COLORS.accent,
        )
        self._scroll_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.content = tk.Frame(self._scroll_canvas, background=COLORS.panel)
        self._content_window = self._scroll_canvas.create_window(
            (0, 0),
            window=self.content,
            anchor="nw",
        )
        self.content.bind("<Configure>", lambda _event: self._sync_scroll_region())
        self._scroll_canvas.bind("<Configure>", self._resize_content_width)
        self._scroll_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._scroll_canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self._scroll_canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _build_header(self) -> None:
        header = tk.Frame(self.content, background=COLORS.panel)
        header.pack(fill=tk.X, padx=18, pady=(18, 12))
        tk.Label(
            header,
            text="PATHFINDING",
            background=COLORS.panel,
            foreground=COLORS.accent,
            font=("TkDefaultFont", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Visualizer",
            background=COLORS.panel,
            foreground=COLORS.text,
            font=("TkDefaultFont", 22, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Build a grid, choose a search, and watch it explore.",
            background=COLORS.panel,
            foreground=COLORS.muted_text,
            font=("TkDefaultFont", 9),
            wraplength=275,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(4, 0))

    def _build_algorithm_section(self) -> None:
        section = self._section("Algorithm")
        combo = ttk.Combobox(
            section,
            textvariable=self.algorithm_var,
            values=tuple(ALGORITHMS),
            state="readonly",
            style="Dark.TCombobox",
            font=("TkDefaultFont", 10),
        )
        combo.pack(fill=tk.X, padx=12, pady=(2, 12))

    def _build_action_section(
        self,
        on_start: Callable[[], None],
        on_pause: Callable[[], None],
        on_resume: Callable[[], None],
        on_stop: Callable[[], None],
        on_clear_path: Callable[[], None],
        on_clear_grid: Callable[[], None],
        on_reset: Callable[[], None],
        on_maze: Callable[[], None],
    ) -> None:
        section = self._section("Controls")
        self.start_button = self._button(
            section,
            "Start visualization",
            on_start,
            background=COLORS.accent,
            active=COLORS.accent_hover,
            foreground="#04111D",
        )
        self.start_button.pack(fill=tk.X, padx=12, pady=(2, 8))

        row = tk.Frame(section, background=COLORS.panel_alt)
        row.pack(fill=tk.X, padx=12, pady=(0, 8))
        for column in range(3):
            row.grid_columnconfigure(column, weight=1, uniform="transport")
        self.pause_button = self._button(row, "Pause", on_pause)
        self.resume_button = self._button(row, "Resume", on_resume)
        self.stop_button = self._button(
            row,
            "Stop",
            on_stop,
            background="#3B1F2B",
            active="#542438",
            foreground="#FDA4AF",
        )
        self.pause_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.resume_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.stop_button.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        row_two = tk.Frame(section, background=COLORS.panel_alt)
        row_two.pack(fill=tk.X, padx=12, pady=(0, 8))
        for column in range(2):
            row_two.grid_columnconfigure(column, weight=1, uniform="clear")
        self._button(row_two, "Clear path", on_clear_path).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        self._button(row_two, "Clear grid", on_clear_grid).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        row_three = tk.Frame(section, background=COLORS.panel_alt)
        row_three.pack(fill=tk.X, padx=12, pady=(0, 12))
        for column in range(2):
            row_three.grid_columnconfigure(column, weight=1, uniform="secondary")
        self._button(row_three, "Reset", on_reset).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        self._button(
            row_three,
            "Random maze",
            on_maze,
            background="#243047",
            active="#2E405F",
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.set_animation_state("ready")

    def _build_tuning_section(self) -> None:
        section = self._section("Tuning")
        tk.Label(
            section,
            textvariable=self.grid_size_text,
            **self._label_options(),
        ).pack(anchor="w", padx=12)
        grid_slider = tk.Scale(
            section,
            from_=self._config.min_columns,
            to=self._config.max_columns,
            orient=tk.HORIZONTAL,
            variable=self.grid_columns_var,
            command=self._on_grid_slider,
            showvalue=False,
            resolution=1,
            background=COLORS.panel_alt,
            foreground=COLORS.text,
            troughcolor=COLORS.border,
            activebackground=COLORS.accent,
            highlightthickness=0,
            borderwidth=0,
            sliderrelief=tk.FLAT,
            length=250,
        )
        grid_slider.pack(fill=tk.X, padx=8, pady=(0, 8))

        tk.Label(
            section,
            textvariable=self.speed_text,
            **self._label_options(),
        ).pack(anchor="w", padx=12)
        speed_slider = tk.Scale(
            section,
            from_=1,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
            command=lambda _value: self._refresh_slider_text(),
            showvalue=False,
            resolution=1,
            background=COLORS.panel_alt,
            foreground=COLORS.text,
            troughcolor=COLORS.border,
            activebackground=COLORS.accent,
            highlightthickness=0,
            borderwidth=0,
            sliderrelief=tk.FLAT,
            length=250,
        )
        speed_slider.pack(fill=tk.X, padx=8, pady=(0, 12))

    def _build_statistics_section(self) -> None:
        section = self._section("Live statistics")
        rows = (
            ("Algorithm", "algorithm"),
            ("Visited nodes", "visited"),
            ("Path length", "path"),
            ("Execution time", "time"),
            ("Grid size", "grid"),
            ("Status", "status"),
            ("FPS", "fps"),
        )
        for index, (label, key) in enumerate(rows):
            self._key_value_row(
                section,
                label,
                self._stat_vars[key],
                bottom_padding=12 if index == len(rows) - 1 else 6,
            )

    def _build_complexity_section(self) -> None:
        section = self._section("Complexity")
        rows = (
            ("Best case", "best"),
            ("Average case", "average"),
            ("Worst case", "worst"),
            ("Space", "space"),
        )
        for label, key in rows:
            self._key_value_row(section, label, self._complexity_vars[key])
        tk.Label(
            section,
            textvariable=self._complexity_vars["note"],
            background=COLORS.panel_alt,
            foreground=COLORS.muted_text,
            font=("TkDefaultFont", 8),
            justify=tk.LEFT,
            wraplength=260,
        ).pack(fill=tk.X, padx=12, pady=(6, 12))

    def _build_legend(self) -> None:
        section = self._section("Legend")
        entries = (
            ("Start", COLORS.start),
            ("End", COLORS.end),
            ("Wall", COLORS.wall),
            ("Visited", COLORS.visited_glow),
            ("Shortest path", COLORS.path),
        )
        grid = tk.Frame(section, background=COLORS.panel_alt)
        grid.pack(fill=tk.X, padx=12, pady=(2, 12))
        for index, (label, color) in enumerate(entries):
            row = index // 2
            column = index % 2
            item = tk.Frame(grid, background=COLORS.panel_alt)
            item.grid(row=row, column=column, sticky="w", padx=(0, 12), pady=3)
            tk.Label(item, text="  ", background=color, width=2).pack(side=tk.LEFT)
            tk.Label(
                item,
                text=label,
                background=COLORS.panel_alt,
                foreground=COLORS.muted_text,
                font=("TkDefaultFont", 8),
            ).pack(side=tk.LEFT, padx=(5, 0))

    def _build_footer(self) -> None:
        tk.Label(
            self.content,
            text=(
                "Left-click to place endpoints or draw walls.\n"
                "Right-click and drag to erase."
            ),
            background=COLORS.panel,
            foreground=COLORS.muted_text,
            font=("TkDefaultFont", 8),
            justify=tk.LEFT,
        ).pack(fill=tk.X, padx=18, pady=(2, 18))

    def _section(self, title: str) -> tk.Frame:
        wrapper = tk.Frame(
            self.content,
            background=COLORS.panel_alt,
            highlightbackground=COLORS.border,
            highlightthickness=1,
        )
        wrapper.pack(fill=tk.X, padx=14, pady=(0, 12))
        tk.Label(
            wrapper,
            text=title.upper(),
            background=COLORS.panel_alt,
            foreground=COLORS.muted_text,
            font=("TkDefaultFont", 8, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 8))
        return wrapper

    @staticmethod
    def _label_options() -> dict[str, object]:
        return {
            "background": COLORS.panel_alt,
            "foreground": COLORS.text,
            "font": ("TkDefaultFont", 9, "bold"),
        }

    def _button(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None],
        *,
        background: str = "#223047",
        active: str = "#2D405E",
        foreground: str = COLORS.text,
    ) -> tk.Button:
        return tk.Button(
            master,
            text=text,
            command=command,
            background=background,
            activebackground=active,
            foreground=foreground,
            activeforeground=foreground,
            disabledforeground="#64748B",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2",
            font=("TkDefaultFont", 9, "bold"),
            padx=9,
            pady=8,
        )

    def _key_value_row(
        self,
        master: tk.Misc,
        label: str,
        value_var: tk.StringVar,
        bottom_padding: int = 6,
    ) -> None:
        row = tk.Frame(master, background=COLORS.panel_alt)
        row.pack(fill=tk.X, padx=12, pady=(0, bottom_padding))
        tk.Label(
            row,
            text=label,
            background=COLORS.panel_alt,
            foreground=COLORS.muted_text,
            font=("TkDefaultFont", 8),
        ).pack(side=tk.LEFT)
        tk.Label(
            row,
            textvariable=value_var,
            background=COLORS.panel_alt,
            foreground=COLORS.text,
            font=("TkDefaultFont", 8, "bold"),
        ).pack(side=tk.RIGHT)

    def _on_algorithm_selected(self, *_args: object) -> None:
        self.update_statistics(algorithm=self.selected_algorithm)
        self.refresh_complexity()

    def _on_grid_slider(self, value: str) -> None:
        columns = int(float(value))
        self.grid_columns_var.set(columns)
        self._refresh_slider_text()
        self._on_grid_size(columns)

    def _refresh_slider_text(self) -> None:
        columns = self.selected_columns
        rows = max(10, round(columns * self._config.row_ratio))
        self.grid_size_text.set(f"Grid size: {columns} × {rows}")
        delay = self.animation_delay_ms
        fps_cap = min(60, round(1_000 / max(1, delay)))
        self.speed_text.set(f"Animation speed: up to {fps_cap} FPS")

    def _speed_value_for_delay(self, delay_ms: int) -> int:
        span = self._config.max_animation_delay_ms - self._config.min_animation_delay_ms
        if span <= 0:
            return 100
        normalized = (self._config.max_animation_delay_ms - delay_ms) / span
        return max(1, min(100, round(normalized * 99 + 1)))

    def _resize_content_width(self, event: tk.Event[tk.Misc]) -> None:
        self._scroll_canvas.itemconfigure(self._content_window, width=event.width)

    def _sync_scroll_region(self) -> None:
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))

    def _on_mousewheel(self, event: tk.Event[tk.Misc]) -> None:
        if not self._event_is_over_panel(event):
            return
        self._scroll_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_mousewheel_linux(self, event: tk.Event[tk.Misc]) -> None:
        if not self._event_is_over_panel(event):
            return
        direction = -1 if event.num == 4 else 1
        self._scroll_canvas.yview_scroll(direction, "units")

    def _event_is_over_panel(self, event: tk.Event[tk.Misc]) -> bool:
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self:
                return True
            widget = getattr(widget, "master", None)
        return False
