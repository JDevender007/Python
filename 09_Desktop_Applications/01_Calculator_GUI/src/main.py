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
        # Bindings are set up by main.py after the view is placed in the window

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
        self.buttons = [
            ("C", "clear", "clear"),
            ("⌫", "backspace", "clear"),
            ("%", "percent", "operator"),
            ("÷", "operator(/)", "operator"),
            
            ("7", "digit(7)", "number"),
            ("8", "digit(8)", "number"),
            ("9", "digit(9)", "number"),
            ("×", "operator(*)", "operator"),
            
            ("4", "digit(4)", "number"),
            ("5", "digit(5)", "number"),
            ("6", "digit(6)", "number"),
            ("−", "operator(-)", "operator"),
            
            ("1", "digit(1)", "number"),
            ("2", "digit(2)", "number"),
            ("3", "digit(3)", "number"),
            ("+", "operator(+)", "operator"),
            
            ("±", "toggle_sign", "clear"),
            ("0", "digit(0)", "number"),
            (".", "digit(.)", "number"),
            ("=", "equals", "equal"),
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

        for i, (text, target, style_class) in enumerate(self.buttons):
            style_name = f"{style_class}.TButton"

            btn = ttk.Button(
                self.buttons_frame,
                text=text,
                command=lambda t=target: self._on_button_click(t),
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

    def _on_button_click(self, target: str) -> None:
        """Handle button clicks - delegated to main.py."""
        pass

    # --- Public API for main.py to configure ---

    def set_display(self, value: str) -> None:
        """Set the display text."""
        self.display_var.set(value)

    def get_display(self) -> str:
        """Get current display value."""
        return self.display_var.get()

    def register_digit_handler(self, handler: Callable[[str], None]) -> None:
        """Register a handler for digit/operator button presses."""
        self._digit_handler = handler

    def register_clear_handler(self, handler: Callable[[], None]) -> None:
        """Register a handler for clear button."""
        self._clear_handler = handler

    def register_backspace_handler(self, handler: Callable[[], None]) -> None:
        """Register a handler for backspace."""
        self._backspace_handler = handler

    def register_equals_handler(self, handler: Callable[[], None]) -> None:
        """Register a handler for equals button."""
        self._equals_handler = handler

    def register_toggle_sign_handler(self, handler: Callable[[], None]) -> None:
        """Register a handler for +/- toggle."""
        self._toggle_sign_handler = handler

    def register_percent_handler(self, handler: Callable[[], None]) -> None:
        """Register a handler for percent."""
        self._percent_handler = handler

    def _on_button_click(self, target: str) -> None:
        """Route button clicks to registered handlers."""
        if target == "clear":
            if hasattr(self, "_clear_handler"):
                self._clear_handler()
        elif target == "backspace":
            if hasattr(self, "_backspace_handler"):
                self._backspace_handler()
        elif target == "equals":
            if hasattr(self, "_equals_handler"):
                self._equals_handler()
        elif target == "toggle_sign":
            if hasattr(self, "_toggle_sign_handler"):
                self._toggle_sign_handler()
        elif target == "percent":
            if hasattr(self, "_percent_handler"):
                self._percent_handler()
        elif target.startswith("digit("):
            digit = target[6:-1]  # Extract digit from "digit(7)"
            if hasattr(self, "_digit_handler"):
                self._digit_handler(digit)
        elif target.startswith("operator("):
            op = target[9:-1]  # Extract operator from "operator(+)"
            if hasattr(self, "_digit_handler"):
                self._digit_handler(op)


def main() -> None:
    """Entry point for the calculator application."""
    root = tk.Tk()
    root.title("Calculator - Python Portfolio")
    root.geometry("320x500")
    root.minsize(300, 400)
    root.maxsize(500, 600)

    # Initialize model and view
    from src.model import CalculatorModel
    model = CalculatorModel()
    view = CalculatorView(root)

    # Wire up display variable
    view.set_display(model.get_display_text())

    # Register handlers with the view
    from src.controller import (
        input_digit,
        input_operator,
        input_percent,
        clear,
        backspace,
        toggle_sign,
        equals,
    )

    view.register_digit_handler(input_digit)
    view.register_clear_handler(clear)
    view.register_backspace_handler(backspace)
    view.register_equals_handler(equals)
    view.register_toggle_sign_handler(toggle_sign)
    view.register_percent_handler(input_percent)

    # Set up keyboard bindings directly on the root window
    root.bind("<Return>", lambda e: equals())
    root.bind("<BackSpace>", lambda e: backspace())
    root.bind("<Escape>", lambda e: clear())

    for key in "0123456789":
        root.bind(key, lambda e, k=key: input_digit(k))
    for key in "+-*/":
        root.bind(key, lambda e, k=key: input_operator(k))
    root.bind(".", lambda e: input_digit("."))

    # Layout
    view.pack(fill="both", expand=True)

    root.mainloop()


if __name__ == "__main__":
    main()