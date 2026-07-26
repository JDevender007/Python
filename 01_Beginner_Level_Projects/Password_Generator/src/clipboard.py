"""
clipboard.py

Copies passwords to the system clipboard.
"""

import pyperclip


class ClipboardManager:
    """Clipboard operations."""

    @staticmethod
    def copy(password: str) -> bool:
        """
        Copy password to the clipboard.

        Returns:
            True if successful, False otherwise.
        """

        try:
            pyperclip.copy(password)
            return True

        except pyperclip.PyperclipException:
            return False

        except Exception:
            return False

    @staticmethod
    def paste() -> str:
        """
        Return clipboard contents.
        """

        try:
            return pyperclip.paste()

        except pyperclip.PyperclipException:
            return ""

        except Exception:
            return ""