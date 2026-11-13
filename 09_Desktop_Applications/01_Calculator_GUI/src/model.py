"""Calculator model - handles all calculation logic."""

from __future__ import annotations
from typing import Optional


class CalculatorModel:
    """Handles all calculation logic for the calculator."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset the calculator state."""
        self.current_input: str = "0"
        self.previous_input: str = ""
        self.operator: Optional[str] = None
        self.should_reset_display: bool = False
        self.history: list[str] = []

    def input_digit(self, digit: str) -> str:
        """Handle digit button presses."""
        if self.current_input == "0" and digit != ".":
            self.current_input = digit
        else:
            if digit == "." and "." in self.current_input:
                return self.current_input
            self.current_input += digit
        return self.current_input

    def input_operator(self, operator: str) -> None:
        """Handle operator button presses."""
        if self.operator is not None and not self.should_reset_display:
            self.evaluate()
        self.operator = operator
        self.previous_input = self.current_input
        self.should_reset_display = True

    def input_percent(self) -> None:
        """Handle percentage button."""
        try:
            value = float(self.current_input) / 100
            self.current_input = str(value)
        except (ValueError, ZeroDivisionError):
            pass

    def evaluate(self) -> str:
        """Evaluate the current expression."""
        if self.operator is None or self.should_reset_display:
            return self.current_input

        try:
            expression = (
                f"{self.previous_input} {self.operator} {self.current_input}"
            )
            result = self._safe_eval(expression)
            self.history.append(expression)
            self.reset()
            self.current_input = str(result)
            self.should_reset_display = True
            return self.current_input
        except ZeroDivisionError:
            raise  # Re-raise for UI to handle
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")

    def _safe_eval(self, expression: str) -> float:
        """Safely evaluate a mathematical expression without eval()."""
        allowed_chars = set("0123456789.+-*/() ")
        if not all(c in allowed_chars for c in expression):
            raise ValueError("Invalid characters in expression")

        # Handle parentheses first
        expr = expression
        while "(" in expr or ")" in expr:
            last_open = expr.rfind("(")
            first_close = expr.find(")", last_open)
            if last_open >= 0 and first_close >= 0:
                inner = expr[last_open + 1 : first_close]
                try:
                    inner_result = self._simple_eval(inner)
                    expr = expr[:last_open] + str(inner_result) + expr[first_close + 1 :]
                except Exception:
                    raise ValueError("Invalid parentheses")

        # Parse: number operator number
        parts = expr.strip().split()
        if len(parts) != 3:
            raise ValueError("Expression must be: number operator number")

        left = float(parts[0])
        operator = parts[1]
        right = float(parts[2])

        if operator == "+":
            return left + right
        elif operator == "-":
            return left - right
        elif operator == "*":
            return left * right
        elif operator == "/":
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left / right
        raise ValueError(f"Unsupported operator: {operator}")

    def _simple_eval(self, expr: str) -> float:
        """Simple evaluation for sub-expressions."""
        parts = expr.split()
        if len(parts) != 3:
            raise ValueError("Invalid sub-expression")
        left = float(parts[0])
        operator = parts[1]
        right = float(parts[2])
        if operator == "+":
            return left + right
        elif operator == "-":
            return left - right
        elif operator == "*":
            return left * right
        elif operator == "/":
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left / right
        raise ValueError(f"Unsupported operator: {operator}")

    def toggle_sign(self) -> str:
        """Toggle positive/negative."""
        try:
            value = float(self.current_input)
            self.current_input = str(-value)
        except ValueError:
            pass
        return self.current_input

    def clear(self) -> None:
        """Clear the calculator."""
        self.reset()

    def backspace(self) -> str:
        """Handle backspace."""
        if len(self.current_input) > 1:
            self.current_input = self.current_input[:-1]
        else:
            self.current_input = "0"
        return self.current_input

    def get_display_text(self) -> str:
        """Get the text to display."""
        return self.current_input