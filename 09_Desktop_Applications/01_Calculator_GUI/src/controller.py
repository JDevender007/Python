"""Calculator controller - connects model and view."""

from __future__ import annotations

from typing import Callable


def input_digit(view: CalculatorView, digit: str) -> None:
    """Handle digit button press through the view."""
    view.set_display(view.model.input_digit(digit))


def input_operator(view: CalculatorView, operator: str) -> None:
    """Handle operator button press."""
    view.model.input_operator(operator)
    view.set_display(view.model.get_display_text())


def input_percent(view: CalculatorView) -> None:
    """Handle percent button."""
    view.model.input_percent()
    view.set_display(view.model.get_display_text())


def clear(view: CalculatorView) -> None:
    """Handle clear button."""
    view.model.clear()
    view.set_display(view.model.get_display_text())


def backspace(view: CalculatorView) -> None:
    """Handle backspace."""
    result = view.model.backspace()
    view.set_display(result)


def toggle_sign(view: CalculatorView) -> None:
    """Handle +/- toggle."""
    result = view.model.toggle_sign()
    view.set_display(result)


def equals(view: CalculatorView) -> None:
    """Handle equals button."""
    try:
        result = view.model.evaluate()
        view.set_display(result)
    except ZeroDivisionError:
        from tkinter import messagebox
        messagebox.showerror("Error", "Cannot divide by zero")
        view.model.clear()
        view.set_display(view.model.get_display_text())
    except ValueError as e:
        from tkinter import messagebox
        messagebox.showerror("Error", str(e))
        view.model.clear()
        view.set_display(view.model.get_display_text())