from __future__ import annotations

"""Application entry point and controller for Sorting Visualizer."""

from collections.abc import Generator
from enum import StrEnum
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import random
import time
import tkinter as tk
from tkinter import messagebox, ttk

from algorithms import ALGORITHMS, SortFrame
from src import config
from src.colors import Palette
from src.controls import ControlPanel
from src.visualizer import VisualizerFrame

LOGGER = logging.getLogger(__name__)


class AppState(StrEnum):
    """Valid lifecycle states for the application."""

    READY = "Ready"
    RUNNING = "Running"
    PAUSED = "Paused"
    STOPPED = "Stopped"
    FINISHED = "Finished"


class SortingVisualizerApp:
    """Single application controller for UI state and animation."""

    def __init__(self, root: tk.Tk) -> None:
        """Initialize the application, widgets, bindings, and first array."""
        self.root = root
        self.state = AppState.READY
        self.values: list[int] = []
        self.colors: list[str] = []
        self.baseline_values: list[int] = []
        self.generator: Generator[SortFrame, None, None] | None = None
        self.animation_job: str | None = None
        self.comparisons = 0
        self.swaps = 0
        self.execution_time = 0.0
        self.started_at = 0.0
        self.paused_at = 0.0
        self.paused_duration = 0.0
        self.step_accumulator = 0.0
        self.finishing = False
        self.finish_index = 0
        self.fullscreen = False
        self.last_tick_at = time.perf_counter()
        self.fps_sample_started = self.last_tick_at
        self.fps_frames = 0
        self.current_fps = 0.0

        self._configure_window()
        self._configure_styles()
        self._build_ui()
        self._bind_shortcuts()
        self.generate_array()
        self.visualizer.update_complexity(self.controls.get_algorithm())
        LOGGER.info("Application initialized")

    def _configure_window(self) -> None:
        self.root.title(f"{config.APP_NAME} {config.APP_VERSION}")
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.minsize(config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT)
        self.root.configure(background=Palette.BACKGROUND)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("App.TFrame", background=Palette.BACKGROUND)
        style.configure("Panel.TFrame", background=Palette.PANEL)
        style.configure(
            "TLabel",
            background=Palette.PANEL,
            foreground=Palette.TEXT,
            font=config.FONT_BODY,
        )
        style.configure(
            "Title.TLabel",
            background=Palette.BACKGROUND,
            foreground=Palette.TEXT,
            font=config.FONT_TITLE,
        )
        style.configure(
            "Heading.TLabel",
            background=Palette.PANEL,
            foreground=Palette.TEXT,
            font=config.FONT_HEADING,
        )
        style.configure(
            "Section.TLabel",
            background=Palette.PANEL,
            foreground=Palette.ACCENT_HOVER,
            font=config.FONT_HEADING,
        )
        style.configure(
            "Muted.TLabel",
            background=Palette.PANEL,
            foreground=Palette.MUTED_TEXT,
            font=config.FONT_SMALL,
        )
        style.configure(
            "Value.TLabel",
            background=Palette.PANEL,
            foreground=Palette.ACCENT_HOVER,
            font=config.FONT_SMALL,
        )
        style.configure(
            "Metric.TLabel",
            background=Palette.PANEL,
            foreground=Palette.TEXT,
            font=config.FONT_MONOSPACE,
        )
        style.configure(
            "Status.TLabel",
            background=Palette.PANEL,
            foreground=Palette.SUCCESS,
            font=config.FONT_HEADING,
        )
        style.configure(
            "TButton",
            background=Palette.BORDER,
            foreground=Palette.TEXT,
            borderwidth=0,
            padding=(12, 8),
            font=config.FONT_BODY,
        )
        style.map(
            "TButton",
            background=[("active", Palette.DISABLED), ("disabled", Palette.PANEL)],
            foreground=[("disabled", Palette.DISABLED)],
        )
        style.configure(
            "Accent.TButton",
            background=Palette.ACCENT,
            foreground=Palette.TEXT,
        )
        style.map("Accent.TButton", background=[("active", Palette.ACCENT_HOVER)])
        style.configure(
            "Danger.TButton",
            background=Palette.DANGER,
            foreground=Palette.TEXT,
        )
        style.map("Danger.TButton", background=[("active", "#F87171")])
        style.configure(
            "TCombobox",
            fieldbackground=Palette.CANVAS,
            background=Palette.CANVAS,
            foreground=Palette.TEXT,
            arrowcolor=Palette.TEXT,
            bordercolor=Palette.BORDER,
            lightcolor=Palette.BORDER,
            darkcolor=Palette.BORDER,
            padding=6,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", Palette.CANVAS)],
            foreground=[("readonly", Palette.TEXT)],
            selectbackground=[("readonly", Palette.CANVAS)],
            selectforeground=[("readonly", Palette.TEXT)],
        )
        style.configure(
            "Horizontal.TScale",
            background=Palette.PANEL,
            troughcolor=Palette.CANVAS,
        )
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=Palette.CANVAS,
            background=Palette.ACCENT,
            bordercolor=Palette.CANVAS,
            lightcolor=Palette.ACCENT,
            darkcolor=Palette.ACCENT,
        )
        style.configure("TSeparator", background=Palette.BORDER)

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, style="App.TFrame", padding=config.CONTENT_PADDING)
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(header, text=config.APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="Generator-driven algorithm animation",
            style="Muted.TLabel",
        ).pack(side="left", padx=(14, 0))
        ttk.Button(header, text="Fullscreen  F11", command=self.toggle_fullscreen).pack(
            side="right"
        )

        self.controls = ControlPanel(
            shell,
            on_start=self.start,
            on_pause=self.pause,
            on_resume=self.resume,
            on_stop=self.stop,
            on_reset=self.reset,
            on_shuffle=self.shuffle_array,
            on_generate=self.generate_array,
            on_size_changed=self.on_size_changed,
            on_algorithm_changed=self.on_algorithm_changed,
        )
        self.controls.grid(row=1, column=0, sticky="nsw", padx=(0, config.CONTENT_PADDING))

        self.visualizer = VisualizerFrame(shell)
        self.visualizer.grid(row=1, column=1, sticky="nsew")

        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(1, weight=1)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<space>", lambda _event: self.start())
        self.root.bind("<Key-p>", lambda _event: self.pause())
        self.root.bind("<Key-P>", lambda _event: self.pause())
        self.root.bind("<Key-r>", lambda _event: self.resume())
        self.root.bind("<Key-R>", lambda _event: self.resume())
        self.root.bind("<Key-s>", lambda _event: self.stop())
        self.root.bind("<Key-S>", lambda _event: self.stop())
        self.root.bind("<Key-n>", lambda _event: self.generate_array())
        self.root.bind("<Key-N>", lambda _event: self.generate_array())
        self.root.bind("<F11>", lambda _event: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda _event: self.close())

    def generate_array(self) -> None:
        """Generate a fresh random array matching the size control."""
        if self.state in {AppState.RUNNING, AppState.PAUSED}:
            return
        size = self.controls.get_array_size()
        population = range(config.MIN_VALUE, config.MAX_VALUE + 1)
        if size <= len(population):
            self.values = random.sample(population, size)
        else:
            self.values = [random.randint(config.MIN_VALUE, config.MAX_VALUE) for _ in range(size)]
        self.baseline_values = self.values.copy()
        self._prepare_idle_state(AppState.READY, "New random array generated.")
        LOGGER.info("Generated random array with %d elements", size)

    def shuffle_array(self) -> None:
        """Shuffle the current values and make the result the reset baseline."""
        if self.state in {AppState.RUNNING, AppState.PAUSED}:
            return
        random.shuffle(self.values)
        self.baseline_values = self.values.copy()
        self._prepare_idle_state(AppState.READY, "Array shuffled.")
        LOGGER.info("Array shuffled")

    def on_size_changed(self, _size: int) -> None:
        """Generate an array after the array-size slider is released."""
        if self.state not in {AppState.RUNNING, AppState.PAUSED}:
            self.generate_array()

    def on_algorithm_changed(self, algorithm: str) -> None:
        """Update metadata when the algorithm selection changes."""
        self.visualizer.update_complexity(algorithm)
        self._update_statistics()
        self.visualizer.set_status(AppState.READY, f"Selected {algorithm}.")

    def start(self) -> None:
        """Start sorting the current array from its current values."""
        if self.state not in {AppState.READY, AppState.STOPPED}:
            return
        try:
            algorithm_name = self.controls.get_algorithm()
            sort_function = ALGORITHMS[algorithm_name]
            self.baseline_values = self.values.copy()
            self.generator = sort_function(self.values)
            self.comparisons = 0
            self.swaps = 0
            self.execution_time = 0.0
            self.started_at = time.perf_counter()
            self.paused_duration = 0.0
            self.step_accumulator = 0.0
            self.finishing = False
            self.finish_index = 0
            self.last_tick_at = self.started_at
            self.fps_sample_started = self.started_at
            self.fps_frames = 0
            self.current_fps = 0.0
            self._set_state(AppState.RUNNING)
            self.visualizer.start_progress()
            self.visualizer.set_status(AppState.RUNNING, f"Sorting with {algorithm_name}.")
            self._schedule_next_frame()
            LOGGER.info("Started %s", algorithm_name)
        except (KeyError, RuntimeError, ValueError) as exc:
            LOGGER.exception("Unable to start sorting")
            messagebox.showerror("Sorting Visualizer", f"Unable to start sorting:\n{exc}")
            self._prepare_idle_state(AppState.STOPPED, "Sorting could not be started.")

    def pause(self) -> None:
        """Pause the animation without losing generator state."""
        if self.state is not AppState.RUNNING or self.finishing:
            return
        self._cancel_animation_job()
        self.paused_at = time.perf_counter()
        self._set_state(AppState.PAUSED)
        self.visualizer.progress.stop()
        self.visualizer.set_status(AppState.PAUSED, "Animation paused.")
        self._update_execution_time()
        self._update_statistics()
        LOGGER.info("Animation paused")

    def resume(self) -> None:
        """Resume a paused animation."""
        if self.state is not AppState.PAUSED or self.generator is None:
            return
        now = time.perf_counter()
        self.paused_duration += now - self.paused_at
        self.last_tick_at = now
        self._set_state(AppState.RUNNING)
        self.visualizer.start_progress()
        self.visualizer.set_status(AppState.RUNNING, "Animation resumed.")
        self._schedule_next_frame()
        LOGGER.info("Animation resumed")

    def stop(self) -> None:
        """Stop the active animation and retain its current visual state."""
        if self.state not in {AppState.RUNNING, AppState.PAUSED}:
            return
        self._cancel_animation_job()
        self._update_execution_time()
        self.generator = None
        self.finishing = False
        self._set_state(AppState.STOPPED)
        self.visualizer.stop_progress(0)
        self.visualizer.set_status(AppState.STOPPED, "Sorting stopped at the current frame.")
        self._update_statistics()
        LOGGER.info("Animation stopped")

    def reset(self) -> None:
        """Restore the baseline array and clear all statistics."""
        self._cancel_animation_job()
        self.values = self.baseline_values.copy()
        self._prepare_idle_state(AppState.READY, "Array reset to its starting order.")
        LOGGER.info("Array reset")

    def _prepare_idle_state(self, state: AppState, detail: str) -> None:
        self._cancel_animation_job()
        self.generator = None
        self.finishing = False
        self.finish_index = 0
        self.comparisons = 0
        self.swaps = 0
        self.execution_time = 0.0
        self.current_fps = 0.0
        self.colors = [Palette.BAR] * len(self.values)
        self._set_state(state)
        self.visualizer.draw(self.values, self.colors)
        self.visualizer.stop_progress(0)
        self.visualizer.set_status(state, detail)
        self._update_statistics()

    def _animation_tick(self) -> None:
        self.animation_job = None
        if self.state is not AppState.RUNNING:
            return

        now = time.perf_counter()
        elapsed = max(0.0, min(0.25, now - self.last_tick_at))
        self.last_tick_at = now
        self._record_fps(now)

        try:
            if self.finishing:
                self._advance_sorted_animation()
            else:
                self.step_accumulator += self.controls.get_speed() * elapsed
                steps = min(config.MAX_STEPS_PER_FRAME, int(self.step_accumulator))
                if steps <= 0:
                    steps = 1 if self.controls.get_speed() >= config.TARGET_FPS else 0
                else:
                    self.step_accumulator -= steps

                for _ in range(steps):
                    if not self._consume_generator_step():
                        break

            self._update_execution_time()
            self._update_statistics()
            if self.state is AppState.RUNNING:
                self._schedule_next_frame()
        except (RuntimeError, tk.TclError, ValueError) as exc:
            LOGGER.exception("Animation failed")
            self._cancel_animation_job()
            self.generator = None
            self._set_state(AppState.STOPPED)
            self.visualizer.stop_progress(0)
            self.visualizer.set_status(AppState.STOPPED, "Animation stopped after an error.")
            messagebox.showerror("Sorting Visualizer", f"Animation error:\n{exc}")

    def _consume_generator_step(self) -> bool:
        if self.generator is None:
            return False
        try:
            values, colors, comparisons, swaps = next(self.generator)
        except StopIteration:
            self._begin_sorted_animation()
            return False

        self.values = values
        self.colors = colors
        self.comparisons = comparisons
        self.swaps = swaps
        self.visualizer.draw(self.values, self.colors)
        return True

    def _begin_sorted_animation(self) -> None:
        self.generator = None
        self.finishing = True
        self.finish_index = 0
        self.colors = [Palette.BAR] * len(self.values)
        self.visualizer.stop_progress(0)
        self.visualizer.set_status(AppState.RUNNING, "Finalizing sorted array.")

    def _advance_sorted_animation(self) -> None:
        count = len(self.values)
        if count == 0:
            self._complete_sort()
            return

        bars_per_frame = max(
            1,
            round(count / (config.SORTED_ANIMATION_SECONDS * config.TARGET_FPS)),
        )
        self.finish_index = min(count, self.finish_index + bars_per_frame)
        self.colors = [
            Palette.SORTED if index < self.finish_index else Palette.BAR
            for index in range(count)
        ]
        self.visualizer.draw(self.values, self.colors)
        self.visualizer.set_progress((self.finish_index / count) * 100)

        if self.finish_index >= count:
            self._complete_sort()

    def _complete_sort(self) -> None:
        self.finishing = False
        self._update_execution_time()
        self._set_state(AppState.FINISHED)
        self.visualizer.stop_progress(100)
        self.visualizer.set_status(AppState.FINISHED, "Array sorted successfully.")
        self._update_statistics()
        LOGGER.info(
            "Sorting finished: comparisons=%d swaps=%d elapsed=%.4f",
            self.comparisons,
            self.swaps,
            self.execution_time,
        )

    def _schedule_next_frame(self) -> None:
        if self.animation_job is None and self.state is AppState.RUNNING:
            self.animation_job = self.root.after(
                config.FRAME_INTERVAL_MS,
                self._animation_tick,
            )

    def _cancel_animation_job(self) -> None:
        if self.animation_job is not None:
            try:
                self.root.after_cancel(self.animation_job)
            except tk.TclError:
                LOGGER.debug("Animation job was already cancelled")
            self.animation_job = None

    def _update_execution_time(self) -> None:
        if self.started_at <= 0:
            return
        reference = self.paused_at if self.state is AppState.PAUSED else time.perf_counter()
        self.execution_time = max(
            0.0,
            reference - self.started_at - self.paused_duration,
        )

    def _record_fps(self, now: float) -> None:
        self.fps_frames += 1
        sample_elapsed = now - self.fps_sample_started
        if sample_elapsed >= config.FPS_SAMPLE_SECONDS:
            self.current_fps = self.fps_frames / sample_elapsed
            self.fps_frames = 0
            self.fps_sample_started = now

    def _update_statistics(self) -> None:
        self.visualizer.update_statistics(
            comparisons=self.comparisons,
            swaps=self.swaps,
            execution_time=self.execution_time,
            algorithm=self.controls.get_algorithm(),
            element_count=len(self.values),
            fps=self.current_fps,
        )

    def _set_state(self, state: AppState) -> None:
        self.state = state
        self.controls.set_application_state(state.value)

    def toggle_fullscreen(self) -> None:
        """Toggle native fullscreen mode."""
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def close(self) -> None:
        """Cancel callbacks and close the application safely."""
        self._cancel_animation_job()
        LOGGER.info("Application closed")
        self.root.destroy()


def configure_logging() -> None:
    """Configure console and rotating-file logging with a safe fallback."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    try:
        log_path = Path.cwd() / "sorting_visualizer.log"
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except OSError:
        LOGGER.warning("File logging unavailable; continuing with console logging")


def main() -> None:
    """Launch the Tkinter application."""
    configure_logging()
    try:
        root = tk.Tk()
        SortingVisualizerApp(root)
        root.mainloop()
    except tk.TclError as exc:
        LOGGER.critical("Tkinter could not initialize: %s", exc)
        raise SystemExit(f"Tkinter could not initialize: {exc}") from exc


if __name__ == "__main__":
    main()
