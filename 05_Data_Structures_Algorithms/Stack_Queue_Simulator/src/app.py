"""Application entry point for Stack Queue Simulator."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from .colors import DARK_PALETTE, ColorPalette
from .config import AppConfig
from .controls import ControlCallbacks, ControlPanel
from .logger import get_logger
from .queue import Queue
from .stack import Stack
from .utils import (
    DataStructureError,
    InputValidationError,
    generate_random_values,
    validate_element,
)
from .visualizer import DataStructureVisualizer


THEORY_CONTENT: dict[str, dict[str, str]] = {
    "Stack": {
        "Definition": (
            "A stack is a linear data structure that follows the Last In, "
            "First Out (LIFO) principle."
        ),
        "Working Principle": (
            "Elements are inserted and removed at one end called the top. "
            "Push adds a new top element, while pop removes the current top."
        ),
        "Time Complexity": (
            "Push: O(1)  •  Pop: O(1)  •  Peek: O(1)  •  Clear: O(n)"
        ),
        "Space Complexity": "O(n), where n is the number of stored elements.",
        "Applications": (
            "Function calls, undo/redo systems, expression evaluation, "
            "backtracking, browser history, and syntax parsing."
        ),
        "Advantages": (
            "Simple constant-time access at the top, predictable behavior, "
            "and efficient memory use for LIFO workflows."
        ),
        "Disadvantages": (
            "Only the top is directly accessible, capacity can be limited, "
            "and searching requires linear time."
        ),
    },
    "Queue": {
        "Definition": (
            "A queue is a linear data structure that follows the First In, "
            "First Out (FIFO) principle."
        ),
        "Working Principle": (
            "Elements enter at the rear and leave from the front. Enqueue adds "
            "an element, while dequeue removes the longest-waiting element."
        ),
        "Time Complexity": (
            "Enqueue: O(1)  •  Dequeue: O(1)  •  Front/Rear: O(1)  •  Clear: O(n)"
        ),
        "Space Complexity": "O(n), where n is the number of stored elements.",
        "Applications": (
            "Task scheduling, print spooling, breadth-first search, message "
            "processing, buffering, and customer-service systems."
        ),
        "Advantages": (
            "Fair processing order, constant-time endpoint operations, and a "
            "natural model for waiting-line workflows."
        ),
        "Disadvantages": (
            "Middle elements are not directly accessible, searching is linear, "
            "and fixed-capacity queues may overflow."
        ),
    },
}


class StatisticsPanel(ttk.LabelFrame):
    """Live application statistics displayed in the right sidebar."""

    def __init__(self, master: tk.Misc, config: AppConfig) -> None:
        super().__init__(
            master,
            text="  LIVE STATISTICS  ",
            style="Card.TLabelframe",
            padding=(14, 14),
        )
        self._config = config
        self._variables: dict[str, tk.StringVar] = {
            "Current Data Structure": tk.StringVar(value="Stack"),
            "Total Elements": tk.StringVar(value="0"),
            "Maximum Capacity": tk.StringVar(value=str(config.capacity)),
            "Operations Performed": tk.StringVar(value="0"),
            "Execution Time": tk.StringVar(value="0.000 ms"),
            "Current Status": tk.StringVar(value="Ready"),
            "FPS Counter": tk.StringVar(value="0.0 FPS"),
        }

        self.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate(self._variables.items()):
            ttk.Label(self, text=label, style="StatKey.TLabel").grid(
                row=row,
                column=0,
                sticky="nw",
                pady=5,
            )
            ttk.Label(
                self,
                textvariable=variable,
                style="StatValue.TLabel",
                wraplength=150,
                justify=tk.RIGHT,
            ).grid(row=row, column=1, sticky="ne", padx=(12, 0), pady=5)

    def update_statistics(
        self,
        *,
        structure: str | None = None,
        total_elements: int | None = None,
        operations: int | None = None,
        execution_ms: float | None = None,
        status: str | None = None,
        fps: float | None = None,
    ) -> None:
        """Update only the supplied statistic values."""

        if structure is not None:
            self._variables["Current Data Structure"].set(structure)
        if total_elements is not None:
            self._variables["Total Elements"].set(str(total_elements))
        if operations is not None:
            self._variables["Operations Performed"].set(str(operations))
        if execution_ms is not None:
            self._variables["Execution Time"].set(f"{execution_ms:.3f} ms")
        if status is not None:
            self._variables["Current Status"].set(status)
        if fps is not None:
            self._variables["FPS Counter"].set(f"{fps:.1f} FPS")


class TheoryPanel(ttk.LabelFrame):
    """Scrollable theory reference for the selected data structure."""

    def __init__(
        self,
        master: tk.Misc,
        config: AppConfig,
        colors: ColorPalette,
    ) -> None:
        super().__init__(
            master,
            text="  THEORY PANEL  ",
            style="Card.TLabelframe",
            padding=(10, 10),
        )
        self._config = config
        self._colors = colors
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._text = tk.Text(
            self,
            wrap=tk.WORD,
            background=colors.panel_alt,
            foreground=colors.text_primary,
            insertbackground=colors.text_primary,
            selectbackground=colors.accent_dark,
            relief=tk.FLAT,
            borderwidth=0,
            padx=10,
            pady=10,
            font=(config.font_family, config.body_font_size),
            cursor="arrow",
        )
        scrollbar = ttk.Scrollbar(
            self,
            orient=tk.VERTICAL,
            command=self._text.yview,
        )
        self._text.configure(yscrollcommand=scrollbar.set)
        self._text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._text.tag_configure(
            "heading",
            foreground=colors.accent,
            font=(config.font_family, config.body_font_size, "bold"),
            spacing1=10,
            spacing3=3,
        )
        self._text.tag_configure(
            "body",
            foreground=colors.text_secondary,
            font=(config.font_family, config.body_font_size),
            lmargin1=2,
            lmargin2=2,
            spacing3=5,
        )
        self.show_structure("Stack")

    def show_structure(self, structure: str) -> None:
        """Replace the theory content with the selected structure details."""

        content = THEORY_CONTENT[structure]
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        for heading, body in content.items():
            self._text.insert(tk.END, f"{heading}\n", "heading")
            self._text.insert(tk.END, f"{body}\n", "body")
        self._text.configure(state=tk.DISABLED)
        self._text.yview_moveto(0.0)


class StackQueueSimulatorApp(tk.Tk):
    """Main Tkinter application coordinating models, controls, and views."""

    def __init__(self) -> None:
        super().__init__()
        self.config_data = AppConfig()
        self.colors = DARK_PALETTE
        self.logger = get_logger("app")

        self.stack: Stack[str] = Stack(self.config_data.capacity)
        self.queue: Queue[str] = Queue(self.config_data.capacity)
        self.current_structure = "Stack"
        self.operations_performed = 0
        self.last_execution_ms = 0.0
        self.is_fullscreen = False

        self._configure_window()
        self._configure_styles()
        self._build_interface()
        self._bind_shortcuts()
        self._refresh_view(status="Ready")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.logger.info("Stack Queue Simulator started.")

    def _configure_window(self) -> None:
        self.title(self.config_data.title)
        self.geometry(
            f"{self.config_data.window_width}x{self.config_data.window_height}"
        )
        self.minsize(
            self.config_data.minimum_width,
            self.config_data.minimum_height,
        )
        self.configure(background=self.colors.background)

        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_position = max(0, (screen_width - self.config_data.window_width) // 2)
        y_position = max(0, (screen_height - self.config_data.window_height) // 2)
        self.geometry(
            f"{self.config_data.window_width}x{self.config_data.window_height}"
            f"+{x_position}+{y_position}"
        )

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            self.logger.debug("The clam theme is unavailable; using the default.")

        style.configure("App.TFrame", background=self.colors.background)
        style.configure("Panel.TFrame", background=self.colors.panel)
        style.configure("Header.TFrame", background=self.colors.panel_alt)
        style.configure("Sidebar.TFrame", background=self.colors.background)

        style.configure(
            "Title.TLabel",
            background=self.colors.panel_alt,
            foreground=self.colors.text_primary,
            font=(
                self.config_data.font_family,
                self.config_data.title_font_size,
                "bold",
            ),
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.colors.panel_alt,
            foreground=self.colors.text_secondary,
            font=(self.config_data.font_family, self.config_data.small_font_size),
        )
        style.configure(
            "Eyebrow.TLabel",
            background=self.colors.panel,
            foreground=self.colors.accent,
            font=(
                self.config_data.font_family,
                self.config_data.small_font_size,
                "bold",
            ),
        )
        style.configure(
            "SectionTitle.TLabel",
            background=self.colors.panel,
            foreground=self.colors.text_primary,
            font=(
                self.config_data.font_family,
                self.config_data.heading_font_size,
                "bold",
            ),
        )
        style.configure(
            "Field.TLabel",
            background=self.colors.panel,
            foreground=self.colors.text_secondary,
            font=(self.config_data.font_family, self.config_data.small_font_size),
        )
        style.configure(
            "Value.TLabel",
            background=self.colors.panel,
            foreground=self.colors.accent,
            font=(
                self.config_data.monospace_font_family,
                self.config_data.small_font_size,
                "bold",
            ),
        )
        style.configure(
            "Hint.TLabel",
            background=self.colors.panel,
            foreground=self.colors.text_muted,
            font=(self.config_data.font_family, self.config_data.small_font_size),
        )
        style.configure(
            "StatKey.TLabel",
            background=self.colors.panel_alt,
            foreground=self.colors.text_secondary,
            font=(self.config_data.font_family, self.config_data.small_font_size),
        )
        style.configure(
            "StatValue.TLabel",
            background=self.colors.panel_alt,
            foreground=self.colors.text_primary,
            font=(
                self.config_data.monospace_font_family,
                self.config_data.small_font_size,
                "bold",
            ),
        )

        style.configure(
            "Card.TLabelframe",
            background=self.colors.panel_alt,
            bordercolor=self.colors.border,
            relief=tk.FLAT,
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=self.colors.background,
            foreground=self.colors.accent,
            font=(
                self.config_data.font_family,
                self.config_data.small_font_size,
                "bold",
            ),
        )

        base_button = {
            "font": (
                self.config_data.font_family,
                self.config_data.small_font_size,
                "bold",
            ),
            "padding": (10, 8),
            "borderwidth": 0,
            "focuscolor": self.colors.panel,
        }
        style.configure(
            "Dark.TButton",
            background=self.colors.panel_alt,
            foreground=self.colors.text_primary,
            **base_button,
        )
        style.map(
            "Dark.TButton",
            background=[
                ("active", self.colors.panel_hover),
                ("pressed", self.colors.border),
            ],
        )
        style.configure(
            "Accent.TButton",
            background=self.colors.accent,
            foreground=self.colors.background,
            **base_button,
        )
        style.map(
            "Accent.TButton",
            background=[
                ("active", self.colors.accent_hover),
                ("pressed", self.colors.accent_dark),
            ],
        )
        style.configure(
            "Danger.TButton",
            background=self.colors.danger,
            foreground=self.colors.background,
            **base_button,
        )
        style.map(
            "Danger.TButton",
            background=[
                ("active", "#FDA4AF"),
                ("pressed", "#BE445A"),
            ],
        )
        style.configure(
            "Wide.TButton",
            background=self.colors.secondary,
            foreground=self.colors.background,
            **base_button,
        )
        style.map(
            "Wide.TButton",
            background=[
                ("active", "#93C5FD"),
                ("pressed", "#3568B2"),
            ],
        )
        style.configure(
            "Header.TButton",
            background=self.colors.panel_alt,
            foreground=self.colors.text_secondary,
            borderwidth=0,
            padding=(12, 8),
            font=(
                self.config_data.font_family,
                self.config_data.small_font_size,
                "bold",
            ),
        )
        style.map(
            "Header.TButton",
            background=[("active", self.colors.panel_hover)],
            foreground=[("active", self.colors.text_primary)],
        )

        style.configure(
            "Dark.TEntry",
            fieldbackground=self.colors.panel_alt,
            foreground=self.colors.text_primary,
            bordercolor=self.colors.border,
            insertcolor=self.colors.text_primary,
            lightcolor=self.colors.border,
            darkcolor=self.colors.border,
            padding=6,
        )
        style.configure(
            "Dark.TCombobox",
            fieldbackground=self.colors.panel_alt,
            background=self.colors.panel_alt,
            foreground=self.colors.text_primary,
            arrowcolor=self.colors.accent,
            bordercolor=self.colors.border,
            lightcolor=self.colors.border,
            darkcolor=self.colors.border,
            padding=6,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", self.colors.panel_alt)],
            foreground=[("readonly", self.colors.text_primary)],
            selectbackground=[("readonly", self.colors.panel_alt)],
            selectforeground=[("readonly", self.colors.text_primary)],
        )
        style.configure(
            "Accent.Horizontal.TScale",
            background=self.colors.panel,
            troughcolor=self.colors.panel_alt,
        )
        style.configure(
            "TPanedwindow",
            background=self.colors.background,
            sashwidth=6,
        )
        style.configure(
            "TSeparator",
            background=self.colors.border,
        )

    def _build_interface(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        header = ttk.Frame(self, style="Header.TFrame", padding=(22, 13))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        logo = tk.Canvas(
            header,
            width=38,
            height=38,
            background=self.colors.panel_alt,
            highlightthickness=0,
        )
        logo.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        logo.create_oval(3, 3, 35, 35, fill=self.colors.accent, outline="")
        logo.create_text(
            19,
            19,
            text="SQ",
            fill=self.colors.background,
            font=(self.config_data.font_family, 9, "bold"),
        )

        ttk.Label(
            header,
            text=self.config_data.title,
            style="Title.TLabel",
        ).grid(row=0, column=1, sticky="sw")
        ttk.Label(
            header,
            text="Interactive data-structure laboratory  •  Python 3.13  •  Tkinter",
            style="Subtitle.TLabel",
        ).grid(row=1, column=1, sticky="nw")

        ttk.Button(
            header,
            text="Fullscreen  F11",
            command=self.toggle_fullscreen,
            style="Header.TButton",
            cursor="hand2",
        ).grid(row=0, column=2, rowspan=2, padx=(10, 4))
        ttk.Button(
            header,
            text="Exit  Esc",
            command=self.close,
            style="Header.TButton",
            cursor="hand2",
        ).grid(row=0, column=3, rowspan=2)

        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL, style="TPanedwindow")
        paned.grid(row=1, column=0, sticky="nsew", padx=10, pady=(10, 10))

        callbacks = ControlCallbacks(
            push=self.push,
            pop=self.pop,
            peek=self.peek,
            enqueue=self.enqueue,
            dequeue=self.dequeue,
            front=self.front,
            rear=self.rear,
            clear=self.clear_selected,
            reset=self.reset,
            random_fill=self.random_fill,
            structure_changed=self.change_structure,
        )
        self.controls = ControlPanel(paned, self.config_data, callbacks)
        self.controls.configure(width=self.config_data.control_panel_width)

        center_frame = ttk.Frame(paned, style="App.TFrame", padding=(8, 0))
        center_frame.rowconfigure(0, weight=1)
        center_frame.columnconfigure(0, weight=1)
        self.visualizer = DataStructureVisualizer(
            center_frame,
            self.config_data,
            self.colors,
            fps_callback=self._update_fps,
        )
        self.visualizer.grid(row=0, column=0, sticky="nsew")

        sidebar = ttk.Frame(paned, style="Sidebar.TFrame", padding=(8, 0, 0, 0))
        sidebar.configure(width=self.config_data.theory_panel_width)
        sidebar.rowconfigure(1, weight=1)
        sidebar.columnconfigure(0, weight=1)

        self.statistics = StatisticsPanel(sidebar, self.config_data)
        self.statistics.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.theory = TheoryPanel(sidebar, self.config_data, self.colors)
        self.theory.grid(row=1, column=0, sticky="nsew")

        paned.add(self.controls, weight=0)
        paned.add(center_frame, weight=1)
        paned.add(sidebar, weight=0)
        self.after(100, lambda: self._set_initial_sashes(paned))

    def _set_initial_sashes(self, paned: ttk.Panedwindow) -> None:
        try:
            total_width = max(paned.winfo_width(), self.config_data.window_width - 20)
            left = self.config_data.control_panel_width
            right_start = total_width - self.config_data.theory_panel_width
            paned.sashpos(0, left)
            paned.sashpos(1, right_start)
        except tk.TclError:
            self.logger.debug("Initial pane positions could not be applied.")

    def _bind_shortcuts(self) -> None:
        bindings: dict[str, Callable[[], None]] = {
            "p": self.push,
            "o": self.pop,
            "e": self.enqueue,
            "d": self.dequeue,
            "c": self.clear_selected,
            "r": self.reset,
        }
        for key, command in bindings.items():
            self.bind_all(
                f"<KeyPress-{key}>",
                lambda event, action=command: self._handle_shortcut(event, action),
                add="+",
            )
            self.bind_all(
                f"<KeyPress-{key.upper()}>",
                lambda event, action=command: self._handle_shortcut(event, action),
                add="+",
            )
        self.bind_all("<F11>", self._on_fullscreen_key, add="+")
        self.bind_all("<Escape>", self._on_escape_key, add="+")

    def _handle_shortcut(
        self,
        _event: tk.Event[tk.Misc],
        command: Callable[[], None],
    ) -> str | None:
        focused = self.focus_get()
        if focused is not None and focused.winfo_class() in {
            "Entry",
            "TEntry",
            "TCombobox",
        }:
            return None
        command()
        return "break"

    def _on_fullscreen_key(self, _event: tk.Event[tk.Misc]) -> str:
        self.toggle_fullscreen()
        return "break"

    def _on_escape_key(self, _event: tk.Event[tk.Misc]) -> str:
        self.close()
        return "break"

    def change_structure(self, structure: str) -> None:
        """Switch the active data structure and refresh the interface."""

        self.current_structure = structure.title()
        self.theory.show_structure(self.current_structure)
        values = self._current_values()
        self.visualizer.display(values, self.current_structure)
        status = f"Switched to {self.current_structure}."
        self.visualizer.show_status(status, "info")
        self._refresh_statistics(status=status)
        self.logger.info("Active structure changed to %s.", self.current_structure)

    def push(self) -> None:
        """Push the entered value onto the stack."""

        started_at = time.perf_counter()
        try:
            value = validate_element(
                self.controls.element_value,
                self.config_data.maximum_input_length,
            )
            self._activate_structure("Stack")
            old_values = self.stack.to_list()
            self.stack.push(value)
            new_values = self.stack.to_list()
        except (InputValidationError, DataStructureError) as exc:
            self._record_failure(started_at, str(exc))
            return

        self.controls.clear_element_input()
        self._record_success(started_at, f"Pushed {value!r} onto the stack.")
        self.visualizer.animate_change(
            old_values,
            new_values,
            "Stack",
            "push",
            self._animation_duration(),
            final_highlights={len(new_values) - 1},
        )

    def pop(self) -> None:
        """Pop the top value from the stack."""

        started_at = time.perf_counter()
        try:
            self._activate_structure("Stack")
            old_values = self.stack.to_list()
            value = self.stack.pop()
            new_values = self.stack.to_list()
        except DataStructureError as exc:
            self._record_failure(started_at, str(exc))
            return

        highlights = {len(new_values) - 1} if new_values else set()
        self._record_success(started_at, f"Popped {value!r} from the stack.")
        self.visualizer.animate_change(
            old_values,
            new_values,
            "Stack",
            "pop",
            self._animation_duration(),
            final_highlights=highlights,
        )

    def peek(self) -> None:
        """Highlight and report the top stack value."""

        started_at = time.perf_counter()
        try:
            self._activate_structure("Stack")
            value = self.stack.peek()
        except DataStructureError as exc:
            self._record_failure(started_at, str(exc))
            return

        values = self.stack.to_list()
        self._record_success(started_at, f"Top element is {value!r}.")
        self.visualizer.display(values, "Stack", {len(values) - 1})
        self.visualizer.show_status(f"Top: {value}", "success")

    def enqueue(self) -> None:
        """Enqueue the entered value at the rear of the queue."""

        started_at = time.perf_counter()
        try:
            value = validate_element(
                self.controls.element_value,
                self.config_data.maximum_input_length,
            )
            self._activate_structure("Queue")
            old_values = self.queue.to_list()
            self.queue.enqueue(value)
            new_values = self.queue.to_list()
        except (InputValidationError, DataStructureError) as exc:
            self._record_failure(started_at, str(exc))
            return

        self.controls.clear_element_input()
        self._record_success(started_at, f"Enqueued {value!r} at the rear.")
        self.visualizer.animate_change(
            old_values,
            new_values,
            "Queue",
            "enqueue",
            self._animation_duration(),
            final_highlights={len(new_values) - 1},
        )

    def dequeue(self) -> None:
        """Dequeue the front value from the queue."""

        started_at = time.perf_counter()
        try:
            self._activate_structure("Queue")
            old_values = self.queue.to_list()
            value = self.queue.dequeue()
            new_values = self.queue.to_list()
        except DataStructureError as exc:
            self._record_failure(started_at, str(exc))
            return

        highlights = {0} if new_values else set()
        self._record_success(started_at, f"Dequeued {value!r} from the front.")
        self.visualizer.animate_change(
            old_values,
            new_values,
            "Queue",
            "dequeue",
            self._animation_duration(),
            final_highlights=highlights,
        )

    def front(self) -> None:
        """Highlight and report the front queue value."""

        started_at = time.perf_counter()
        try:
            self._activate_structure("Queue")
            value = self.queue.front()
        except DataStructureError as exc:
            self._record_failure(started_at, str(exc))
            return

        self._record_success(started_at, f"Front element is {value!r}.")
        self.visualizer.display(self.queue.to_list(), "Queue", {0})
        self.visualizer.show_status(f"Front: {value}", "success")

    def rear(self) -> None:
        """Highlight and report the rear queue value."""

        started_at = time.perf_counter()
        try:
            self._activate_structure("Queue")
            value = self.queue.rear()
        except DataStructureError as exc:
            self._record_failure(started_at, str(exc))
            return

        values = self.queue.to_list()
        self._record_success(started_at, f"Rear element is {value!r}.")
        self.visualizer.display(values, "Queue", {len(values) - 1})
        self.visualizer.show_status(f"Rear: {value}", "success")

    def clear_selected(self) -> None:
        """Clear the currently selected data structure."""

        started_at = time.perf_counter()
        old_values = self._current_values()
        if self.current_structure == "Stack":
            self.stack.clear()
        else:
            self.queue.clear()

        status = f"Cleared the {self.current_structure.lower()}."
        self._record_success(started_at, status)
        if old_values:
            self.visualizer.animate_change(
                old_values,
                [],
                self.current_structure,
                "clear",
                self._animation_duration(),
            )
        else:
            self.visualizer.display([], self.current_structure)
            self.visualizer.show_status(
                f"{self.current_structure} was already empty.",
                "warning",
            )

    def reset(self) -> None:
        """Clear both structures and restore initial application state."""

        started_at = time.perf_counter()
        previous_structure = self.current_structure
        old_values = self._current_values()
        self.stack.clear()
        self.queue.clear()
        self.current_structure = "Stack"
        self.controls.select_structure("Stack", notify=False)
        self.theory.show_structure("Stack")
        self.operations_performed = 0
        self.last_execution_ms = (time.perf_counter() - started_at) * 1000
        self._refresh_statistics(status="Application reset.")
        self.visualizer.animate_change(
            old_values,
            [],
            previous_structure,
            "reset",
            self._animation_duration(),
            on_complete=lambda: self.visualizer.display([], "Stack"),
        )
        self.visualizer.show_status("Application reset.", "success")
        self.logger.info("Application state reset.")

    def random_fill(self) -> None:
        """Replace the active structure with randomly generated values."""

        started_at = time.perf_counter()
        count = min(
            self.controls.random_fill_count,
            self.config_data.capacity,
        )
        values = generate_random_values(
            count,
            self.config_data.random_minimum,
            self.config_data.random_maximum,
        )
        old_values = self._current_values()

        if self.current_structure == "Stack":
            self.stack.clear()
            for value in values:
                self.stack.push(value)
            new_values = self.stack.to_list()
        else:
            self.queue.clear()
            for value in values:
                self.queue.enqueue(value)
            new_values = self.queue.to_list()

        self._record_success(
            started_at,
            (
                f"Filled the {self.current_structure.lower()} with "
                f"{count} random elements."
            ),
        )
        self.visualizer.animate_change(
            old_values,
            new_values,
            self.current_structure,
            "random_fill",
            self._animation_duration(),
            final_highlights={len(new_values) - 1} if new_values else set(),
        )

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""

        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        status = "Fullscreen enabled." if self.is_fullscreen else "Fullscreen disabled."
        self._refresh_statistics(status=status)
        self.visualizer.show_status(status, "info")

    def close(self) -> None:
        """Close the application cleanly."""

        self.logger.info("Stack Queue Simulator closed.")
        self.destroy()

    def _activate_structure(self, structure: str) -> None:
        normalized = structure.title()
        if self.current_structure == normalized:
            return
        self.current_structure = normalized
        self.controls.select_structure(normalized, notify=False)
        self.theory.show_structure(normalized)

    def _record_success(self, started_at: float, status: str) -> None:
        self.operations_performed += 1
        self.last_execution_ms = (time.perf_counter() - started_at) * 1000
        self._refresh_statistics(status=status)
        self.visualizer.show_status(status, "success")
        self.logger.info(status)

    def _record_failure(self, started_at: float, status: str) -> None:
        self.operations_performed += 1
        self.last_execution_ms = (time.perf_counter() - started_at) * 1000
        self._refresh_statistics(status=status)
        self.visualizer.display(self._current_values(), self.current_structure)
        self.visualizer.show_status(status, "danger")
        self.bell()
        self.logger.warning(status)

    def _refresh_view(self, status: str) -> None:
        self.visualizer.display(self._current_values(), self.current_structure)
        self.theory.show_structure(self.current_structure)
        self._refresh_statistics(status=status)

    def _refresh_statistics(self, status: str | None = None) -> None:
        self.statistics.update_statistics(
            structure=self.current_structure,
            total_elements=len(self._current_values()),
            operations=self.operations_performed,
            execution_ms=self.last_execution_ms,
            status=status,
        )

    def _update_fps(self, fps: float) -> None:
        self.statistics.update_statistics(fps=fps)

    def _current_values(self) -> list[str]:
        return (
            self.stack.to_list()
            if self.current_structure == "Stack"
            else self.queue.to_list()
        )

    def _animation_duration(self) -> int:
        return self.config_data.animation_duration(self.controls.speed_multiplier)


def main() -> None:
    """Create and run the desktop application."""

    app = StackQueueSimulatorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
