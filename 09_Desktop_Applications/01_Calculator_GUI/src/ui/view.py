"""Calculator view - the graphical user interface."""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional


class CalculatorView(ttk.Frame):
    """The calculator's graphical user interface."""

    def __init__(self, master: tk.Tk, **kwargs: any) -> None:
        super().__init__(master, **kwargs)
        self.master = master
        self._create_widgets()
        self._setup_layout()
        self._setup_bindings()

    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        # Display frame
        self.display_frame = ttk.Frame(self)

        self.display_var = tk.StringVar(value="0")
        self.display_entry = ttk.Entry(
            self.display_frame,
            textvariable=self.display_var,
            font=("Segoe UI", 24),
            justify="right",
            state="readonly",
        )

        # Buttons frame
        self.buttons_frame = ttk.Frame(self)

        # Button definitions: (text, command, style_class)
        # style_class determines ttk style: "number", "operator", "clear", "equal"
        self.buttons = [
            ("C", self._on_clear, "clear"),
            ("⌫", self._on_backspace, "clear"),
            ("%", self._on_percent, "operator"),
            ("÷", lambda: self._on_operator("/"), "operator"),
            
            ("7", lambda: self._on_digit("7"), "number"),
            ("8", lambda: self._on_digit("8"), "number"),
            ("9", lambda: self._on_digit("9"), "number"),
            ("×", lambda: self._on_operator("*"), "operator"),
            
            ("4", lambda: self._on_digit("4"), "number"),
            ("5", lambda: self._on_digit("5"), "number"),
            ("6", lambda: self._on_digit("6"), "number"),
            ("−", lambda: self._on_operator("-"), "operator"),
            
            ("1", lambda: self._on_digit("1"), "number"),
            ("2", lambda: self._on_digit("2"), "number"),
            ("3", lambda: self._on_digit("3"), "number"),
            ("+", lambda: self._on_operator("+"), "operator"),
            
            ("±", self._on_toggle_sign, "clear"),
            ("0", lambda: self._on_digit("0"), "number"),
            (".", lambda: self._on_digit("."), "number"),
            ("=", self._on_equals, "equal"),
        ]

    def _create_buttons(self) -> None:
        """Create and grid all buttons."""
        # Configure styles
        style = ttk.Style()
        style.configure("Number.TButton", font=("Segoe UI", 14))
        style.configure("Operator.TButton", font=("Segoe UI", 14))
        style.configure("Clear.TButton", font=("Segoe UI", 14))
        style.configure("Equal.TButton", font=("Segoe UI", 14))

        # Grid buttons
        row_val = 0
        col_val = 0

        for i, (text, command, style_class) in enumerate(self.buttons):
            # Map style class to ttk style name
            style_name = f"{style_class}.TButton"

            btn = ttk.Button(
                self.buttons_frame,
                text=text,
                command=command,
                style=style_name,
            )
            btn.grid(row=row_val, column=col_val, padx=2, pady=2, sticky="nsew")

            col_val += 1
            if col_val > 3:
                col_val = 0
                row_val += 1

        # Configure grid weights for expansion
        for i in range(4):
            self.buttons_frame.grid_columnconfigure(i, weight=1)

    def _setup_layout(self) -> None:
        """Set up the main layout."""
        self.display_frame.pack(fill="x", padx=10, pady=10)
        self.buttons_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Display field
        self.display_entry.pack(fill="x", padx=5, pady=5)

    def _setup_bindings(self) -> None:
        """Set up keyboard and event bindings."""
        self.master.bind("<Return>", lambda e: self._on_equals())
        self.master.bind("<BackSpace>", lambda e: self._on_backspace())
        self.master.bind("<Escape>", lambda e: self._on_clear())

        # Bind number and operator keys (excluding space)
        for key in "0123456789+-*/.":
            self.master.bind(f"<KeyPress-{key}>", lambda e, k=key: self._on_key_press(k))

    def _on_key_press(self, key: str) -> None:
        """Handle keyboard input events."""
        if key in "0123456789":
            self._on_digit(key)
        elif key in "+-*/":
            self._on_operator(key)
        elif key == ".":
            self._on_digit(".")
        elif key == "=":
            self._on_equals()

    # --- Button command handlers ---

    def _on_digit(self, digit: str) -> None:
        """Handle digit button press."""
        from . import controller  # Lazy import to avoid circular
        controller.input_digit(self, digit)

    def _on_operator(self, operator: str) -> None:
        """Handle operator button press."""
        from . import controller
        controller.input_operator(self, operator)

    def _on_percent(self) -> None:
        """Handle percent button."""
        from . import controller
        controller.input_percent(self)

    def _on_clear(self) -> None:
        """Handle clear button."""
        from . import controller
        controller.clear(self)

    def _on_backspace(self) -> None:
        """Handle backspace."""
        from . import controller
        controller.backspace(self)

    def _on_toggle_sign(self) -> None:
        """Handle +/- toggle."""
        from . import controller
        controller.toggle_sign(self)

    def _on_equals(self) -> None:
        """Handle equals button."""
        from . import controller
        controller.equals(self)

    # --- Public API for model updates ---

    def set_display(self, value: str) -> None:
        """Set the display text."""
        self.display_var.set(value)

    def get_display(self) -> str:
        """Get current display value."""
        return self.display_var.get()


# Add lazy controller imports at module level to avoid circular imports
# These will be populated when the package is fully loaded
_controller_instance = None


def set_controller(controller_instance) -> None:
    """Set the controller instance for lazy imports."""
    global _controller_instance
    _controller_instance = controller_instance