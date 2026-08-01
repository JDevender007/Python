"""Main application controller for Binary Search Visualizer."""

from __future__ import annotations

# Allow `python src/app.py` as well as `python -m src.app`.
if __name__ == "__main__" and __package__ is None:
    import runpy
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    runpy.run_module("src.app", run_name="__main__")
    raise SystemExit(0)

import random
import time
import tkinter as tk
from collections.abc import Generator
from tkinter import messagebox, ttk

from .binary_search import (
    SearchStep,
    binary_search_steps,
    linear_search_steps,
)
from .complexity import ComplexityPanel
from .config import (
    ALGORITHM_BINARY,
    APP_NAME,
    APP_VERSION,
    AppState,
    CONTROL_PANEL_WIDTH,
    DEFAULT_ARRAY_SIZE,
    FONT_BODY,
    FONT_BUTTON,
    FONT_SMALL,
    FONT_TITLE,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    PALETTE,
    PANEL_PADDING,
    TARGET_FPS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from .controls import ControlCallbacks, ControlPanel, StatisticsPanel
from .logger import LOGGER
from .utils import (
    InputValidationError,
    generate_sorted_array,
    parse_custom_array,
    validate_search_target,
)
from .visualizer import ArrayVisualizer


class BinarySearchVisualizerApp:
    """Coordinate GUI controls, search generators, and animation state."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.array: list[int] = []
        self.initial_array: list[int] = []
        self.generator: Generator[SearchStep, None, None] | None = None
        self.state = AppState.IDLE
        self.target: int | None = None
        self.current_step = 0
        self.comparisons = 0
        self.search_started_at = 0.0
        self.pause_started_at = 0.0
        self.total_paused_time = 0.0
        self.last_step: SearchStep | None = None
        self._pending_animation_step: SearchStep | None = None
        self.search_finished_at = 0.0
        self._stats_after_id: str | None = None
        self._fullscreen = False

        self._configure_root()
        self._configure_styles()
        self._build_layout()
        self._bind_shortcuts()
        self.generate_array()
        self._schedule_stats_refresh()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        LOGGER.info("%s %s started", APP_NAME, APP_VERSION)

    def _configure_root(self) -> None:
        self.root.title(f"{APP_NAME} · v{APP_VERSION}")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.root.configure(background=PALETTE.background)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            LOGGER.warning("The clam ttk theme is unavailable")

        style.configure("App.TFrame", background=PALETTE.background)
        style.configure(
            "Card.TFrame",
            background=PALETTE.surface,
            relief="flat",
        )
        style.configure(
            "TLabel",
            background=PALETTE.background,
            foreground=PALETTE.text,
            font=FONT_BODY,
        )
        style.configure(
            "Card.TLabel",
            background=PALETTE.surface,
            foreground=PALETTE.text,
        )
        style.configure(
            "CardTitle.TLabel",
            background=PALETTE.surface,
            foreground=PALETTE.text,
        )
        style.configure(
            "Muted.TLabel",
            background=PALETTE.surface,
            foreground=PALETTE.muted_text,
        )
        style.configure(
            "Accent.TLabel",
            background=PALETTE.surface,
            foreground=PALETTE.accent,
        )
        style.configure(
            "TEntry",
            fieldbackground=PALETTE.input_background,
            foreground=PALETTE.text,
            insertcolor=PALETTE.text,
            bordercolor=PALETTE.border,
            lightcolor=PALETTE.border,
            darkcolor=PALETTE.border,
            padding=7,
        )
        style.map(
            "TEntry",
            fieldbackground=[("disabled", PALETTE.surface_alt)],
            foreground=[("disabled", PALETTE.muted_text)],
        )
        style.configure(
            "TCombobox",
            fieldbackground=PALETTE.input_background,
            background=PALETTE.surface_alt,
            foreground=PALETTE.text,
            arrowcolor=PALETTE.text,
            bordercolor=PALETTE.border,
            padding=6,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", PALETTE.input_background)],
            selectbackground=[("readonly", PALETTE.input_background)],
            selectforeground=[("readonly", PALETTE.text)],
        )
        style.configure(
            "TScale",
            background=PALETTE.surface,
            troughcolor=PALETTE.surface_alt,
        )
        style.configure(
            "Primary.TButton",
            background=PALETTE.accent,
            foreground=PALETTE.text,
            borderwidth=0,
            padding=(10, 8),
            font=FONT_BUTTON,
        )
        style.map(
            "Primary.TButton",
            background=[
                ("active", PALETTE.accent_hover),
                ("disabled", PALETTE.disabled),
            ],
        )
        style.configure(
            "Secondary.TButton",
            background=PALETTE.surface_alt,
            foreground=PALETTE.text,
            borderwidth=0,
            padding=(10, 8),
            font=FONT_BUTTON,
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("active", PALETTE.border),
                ("disabled", PALETTE.disabled),
            ],
        )
        style.configure(
            "Success.TButton",
            background=PALETTE.found_element,
            foreground=PALETTE.background,
            borderwidth=0,
            padding=(10, 8),
            font=FONT_BUTTON,
        )
        style.map(
            "Success.TButton",
            background=[
                ("active", "#55E58C"),
                ("disabled", PALETTE.disabled),
            ],
        )
        style.configure(
            "Danger.TButton",
            background=PALETTE.not_found,
            foreground=PALETTE.text,
            borderwidth=0,
            padding=(10, 8),
            font=FONT_BUTTON,
        )
        style.map(
            "Danger.TButton",
            background=[
                ("active", "#FF6B78"),
                ("disabled", PALETTE.disabled),
            ],
        )

        self.root.option_add("*TCombobox*Listbox.background", PALETTE.surface_alt)
        self.root.option_add("*TCombobox*Listbox.foreground", PALETTE.text)
        self.root.option_add("*TCombobox*Listbox.selectBackground", PALETTE.selection)

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, style="App.TFrame", padding=PANEL_PADDING)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=0, minsize=CONTROL_PANEL_WIDTH)
        container.rowconfigure(1, weight=1)

        header = ttk.Frame(container, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="Binary Search Visualizer",
            font=FONT_TITLE,
            foreground=PALETTE.text,
            background=PALETTE.background,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Interactive algorithm analysis with smooth step animation",
            font=FONT_SMALL,
            foreground=PALETTE.muted_text,
            background=PALETTE.background,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(
            header,
            text="F11 Fullscreen  •  Esc Exit",
            font=FONT_SMALL,
            foreground=PALETTE.muted_text,
            background=PALETTE.background,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        canvas_card = ttk.Frame(
            container,
            style="Card.TFrame",
            padding=PANEL_PADDING,
        )
        canvas_card.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        canvas_card.rowconfigure(1, weight=1)
        canvas_card.columnconfigure(0, weight=1)

        self.status_heading = tk.StringVar(value="Ready")
        ttk.Label(
            canvas_card,
            textvariable=self.status_heading,
            style="CardTitle.TLabel",
            font=FONT_BODY,
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.visualizer = ArrayVisualizer(canvas_card)
        self.visualizer.grid(row=1, column=0, sticky="nsew")

        sidebar = ttk.Frame(container, style="App.TFrame")
        sidebar.grid(row=1, column=1, sticky="nsew")
        sidebar.columnconfigure(0, weight=1)

        callbacks = ControlCallbacks(
            generate=self.generate_array,
            apply_custom_array=self.apply_custom_array,
            start=self.start_search,
            pause=self.pause_search,
            resume=self.resume_search,
            stop=self.stop_search,
            reset=self.reset_search,
            shuffle=self.shuffle_array,
            algorithm_changed=self.on_algorithm_changed,
        )
        self.controls = ControlPanel(sidebar, callbacks)
        self.controls.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.statistics = StatisticsPanel(sidebar)
        self.statistics.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self.complexity = ComplexityPanel(sidebar)
        self.complexity.grid(row=2, column=0, sticky="ew")

    def _bind_shortcuts(self) -> None:
        self.root.bind("<space>", self._shortcut_start)
        self.root.bind("<KeyPress-p>", lambda _event: self.pause_search())
        self.root.bind("<KeyPress-P>", lambda _event: self.pause_search())
        self.root.bind("<KeyPress-r>", lambda _event: self.resume_search())
        self.root.bind("<KeyPress-R>", lambda _event: self.resume_search())
        self.root.bind("<KeyPress-s>", lambda _event: self.stop_search())
        self.root.bind("<KeyPress-S>", lambda _event: self.stop_search())
        self.root.bind("<KeyPress-n>", lambda _event: self.generate_array())
        self.root.bind("<KeyPress-N>", lambda _event: self.generate_array())
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", lambda _event: self.close())

    def generate_array(self) -> None:
        """Generate and display a new sorted random array."""

        if self.state in (AppState.RUNNING, AppState.PAUSED):
            self.stop_search()
        size = (
            int(self.controls.array_size_var.get())
            if hasattr(self, "controls")
            else DEFAULT_ARRAY_SIZE
        )
        self.array = generate_sorted_array(size)
        self.initial_array = self.array.copy()
        self._clear_search_state()
        self.visualizer.set_data(self.array)
        self.status_heading.set("New sorted array generated")
        self._set_state(AppState.IDLE)
        LOGGER.info("Generated array with %d elements", size)

    def apply_custom_array(self) -> None:
        """Parse, sort, and display an array entered by the user."""

        try:
            values = parse_custom_array(self.controls.custom_array_var.get())
        except InputValidationError as exc:
            self._show_validation_error(str(exc))
            return

        if self.state in (AppState.RUNNING, AppState.PAUSED):
            self.stop_search()
        self.array = values
        self.initial_array = values.copy()
        self._clear_search_state()
        self.visualizer.set_data(self.array)
        self.status_heading.set("Custom array applied and sorted")
        self._set_state(AppState.IDLE)
        LOGGER.info("Applied custom array with %d elements", len(values))

    def shuffle_array(self) -> None:
        """Shuffle the current array for linear-search exploration."""

        if not self.array:
            return
        if self.state in (AppState.RUNNING, AppState.PAUSED):
            self.stop_search()
        random.shuffle(self.array)
        self.initial_array = self.array.copy()
        self._clear_search_state()
        self.visualizer.set_data(self.array)
        self.status_heading.set(
            "Array shuffled · Binary Search will sort automatically"
        )
        self._set_state(AppState.IDLE)
        LOGGER.info("Array shuffled")

    def start_search(self) -> None:
        """Validate input, create the selected generator, and start animation."""

        if self.state == AppState.PAUSED:
            self.resume_search()
            return
        if self.state == AppState.RUNNING:
            return

        try:
            self.target = validate_search_target(self.controls.target_var.get())
        except InputValidationError as exc:
            self._show_validation_error(str(exc))
            self.controls.focus_target()
            return

        if not self.array:
            self.generate_array()

        algorithm = self.controls.algorithm_var.get()
        if algorithm == ALGORITHM_BINARY:
            self.array.sort()
            self.visualizer.set_data(self.array)
            self.generator = binary_search_steps(self.array, self.target)
        else:
            self.generator = linear_search_steps(self.array, self.target)

        self.current_step = 0
        self.comparisons = 0
        self.last_step = None
        self.search_started_at = time.perf_counter()
        self.search_finished_at = 0.0
        self.total_paused_time = 0.0
        self.pause_started_at = 0.0
        self.status_heading.set(f"Searching for {self.target}…")
        self._set_state(AppState.RUNNING)
        LOGGER.info("Started %s for target %s", algorithm, self.target)
        self._advance_search()

    def pause_search(self) -> None:
        """Pause active animation while preserving generator state."""

        if self.state != AppState.RUNNING:
            return
        self.visualizer.cancel_animation()
        self.pause_started_at = time.perf_counter()
        self.status_heading.set("Search paused")
        self._set_state(AppState.PAUSED)
        LOGGER.info("Search paused")

    def resume_search(self) -> None:
        """Resume a previously paused search."""

        if self.state != AppState.PAUSED:
            return
        if self.pause_started_at:
            self.total_paused_time += time.perf_counter() - self.pause_started_at
            self.pause_started_at = 0.0
        self.status_heading.set(f"Searching for {self.target}…")
        self._set_state(AppState.RUNNING)
        LOGGER.info("Search resumed")
        if self._pending_animation_step is not None:
            self._animate_pending_step()
        else:
            self._advance_search()

    def stop_search(self) -> None:
        """Stop the active search and keep the current visualization."""

        if self.state not in (AppState.RUNNING, AppState.PAUSED):
            return
        self.visualizer.cancel_animation()
        self.generator = None
        self._pending_animation_step = None
        self.search_finished_at = time.perf_counter()
        self.status_heading.set("Search stopped")
        self._set_state(AppState.STOPPED)
        LOGGER.info("Search stopped")

    def reset_search(self) -> None:
        """Restore the most recently generated or supplied array."""

        self.visualizer.cancel_animation()
        self.array = self.initial_array.copy()
        self._clear_search_state()
        self.visualizer.set_data(self.array)
        self.status_heading.set("Visualization reset")
        self._set_state(AppState.IDLE)
        LOGGER.info("Visualization reset")

    def on_algorithm_changed(self, algorithm: str) -> None:
        """Reset transient state when the selected algorithm changes."""

        if self.state in (AppState.RUNNING, AppState.PAUSED):
            self.stop_search()
        self._clear_search_state()
        self.visualizer.set_data(self.array)
        self.status_heading.set(f"{algorithm} selected")
        self._set_state(AppState.IDLE)

    def toggle_fullscreen(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        """Toggle fullscreen mode and return a Tk event break marker."""

        self._fullscreen = not self._fullscreen
        self.root.attributes("-fullscreen", self._fullscreen)
        return "break"

    def close(self) -> None:
        """Cancel scheduled work and close the application cleanly."""

        self.visualizer.cancel_animation()
        if self._stats_after_id is not None:
            try:
                self.root.after_cancel(self._stats_after_id)
            except tk.TclError:
                pass
        LOGGER.info("Application closed")
        self.root.destroy()

    def _advance_search(self) -> None:
        if self.state != AppState.RUNNING or self.generator is None:
            return

        try:
            step = next(self.generator)
        except StopIteration:
            self._complete_search()
            return
        except Exception as exc:
            LOGGER.exception("Search execution failed")
            self.generator = None
            self.status_heading.set("Search failed")
            self._set_state(AppState.STOPPED)
            messagebox.showerror(
                "Search Error",
                f"The search could not continue:\n{exc}",
                parent=self.root,
            )
            return

        self.last_step = step
        self._pending_animation_step = step
        array, colors, left, right, middle, current, comparisons = step
        self.array = array.copy()
        self.current_step += 1
        self.comparisons = comparisons
        self._describe_step(left, right, middle, current, colors)
        self._animate_pending_step()

    def _animate_pending_step(self) -> None:
        """Animate the current yielded state, including after a pause."""

        if self.state != AppState.RUNNING or self._pending_animation_step is None:
            return
        array, colors, *_indices = self._pending_animation_step
        delay = int(self.controls.speed_var.get())
        self.visualizer.animate_to(
            array,
            colors,
            delay,
            on_complete=self._finish_step_animation,
        )

    def _finish_step_animation(self) -> None:
        """Mark a visual step complete and request the next generator state."""

        if self.state != AppState.RUNNING:
            return
        self._pending_animation_step = None
        self._advance_search()

    def _complete_search(self) -> None:
        self.generator = None
        self._pending_animation_step = None
        self.search_finished_at = time.perf_counter()
        found = False
        found_index = -1
        if self.last_step is not None:
            array, colors, _left, _right, middle, current, _comparisons = self.last_step
            candidate = middle if middle >= 0 else current
            if (
                candidate >= 0
                and candidate < len(array)
                and self.target is not None
                and array[candidate] == self.target
                and colors[candidate] == PALETTE.found_element
            ):
                found = True
                found_index = candidate

        if found:
            self.status_heading.set(
                f"Found {self.target} at index {found_index}"
            )
        else:
            self.status_heading.set(f"{self.target} was not found")
        self._set_state(AppState.COMPLETED)
        LOGGER.info(
            "Search completed: found=%s comparisons=%d",
            found,
            self.comparisons,
        )

    def _describe_step(
        self,
        left: int,
        right: int,
        middle: int,
        current: int,
        colors: list[str],
    ) -> None:
        if PALETTE.found_element in colors:
            index = middle if middle >= 0 else current
            self.status_heading.set(f"Target found at index {index}")
        elif colors and all(color == PALETTE.not_found for color in colors):
            self.status_heading.set("Search range exhausted · target not found")
        elif middle >= 0:
            self.status_heading.set(
                f"Range [{left}, {right}] · checking middle index {middle}"
            )
        else:
            self.status_heading.set(f"Checking index {current}")

    def _clear_search_state(self) -> None:
        self.generator = None
        self.target = None
        self.current_step = 0
        self.comparisons = 0
        self.search_started_at = 0.0
        self.pause_started_at = 0.0
        self.total_paused_time = 0.0
        self.last_step = None
        self._pending_animation_step = None
        self.search_finished_at = 0.0

    def _set_state(self, state: AppState) -> None:
        self.state = state
        is_running = state == AppState.RUNNING
        is_paused = state == AppState.PAUSED
        is_busy = is_running or is_paused
        self.controls.set_button_states(
            {
                "generate": not is_busy,
                "shuffle": not is_busy and bool(self.array),
                "start": not is_busy,
                "pause": is_running,
                "resume": is_paused,
                "stop": is_busy,
                "reset": state != AppState.IDLE or self.current_step > 0,
            }
        )
        self._refresh_statistics()

    def _elapsed_time(self) -> float:
        if not self.search_started_at:
            return 0.0
        if self.state == AppState.PAUSED and self.pause_started_at:
            endpoint = self.pause_started_at
        elif self.search_finished_at:
            endpoint = self.search_finished_at
        else:
            endpoint = time.perf_counter()
        return max(0.0, endpoint - self.search_started_at - self.total_paused_time)

    def _refresh_statistics(self) -> None:
        if not hasattr(self, "statistics"):
            return
        self.statistics.update_stats(
            current_algorithm=self.controls.algorithm_var.get(),
            comparisons=self.comparisons,
            execution_time=f"{self._elapsed_time() * 1000:.1f} ms",
            current_step=self.current_step,
            array_size=len(self.array),
            search_value=self.target if self.target is not None else "—",
            status=self.state.value,
            fps_counter=(
                f"{self.visualizer.fps:.0f} / {TARGET_FPS}"
                if self.visualizer.fps > 0
                else f"— / {TARGET_FPS}"
            ),
        )

    def _schedule_stats_refresh(self) -> None:
        self._refresh_statistics()
        self._stats_after_id = self.root.after(
            100,
            self._schedule_stats_refresh,
        )

    def _shortcut_start(self, _event: tk.Event[tk.Misc]) -> str:
        focused = self.root.focus_get()
        if isinstance(focused, (ttk.Entry, tk.Entry, ttk.Combobox)):
            return "break"
        self.start_search()
        return "break"

    def _show_validation_error(self, message: str) -> None:
        LOGGER.warning("Input validation failed: %s", message)
        messagebox.showwarning("Invalid Input", message, parent=self.root)


def main() -> None:
    """Launch the Tkinter application."""

    root = tk.Tk()
    BinarySearchVisualizerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
