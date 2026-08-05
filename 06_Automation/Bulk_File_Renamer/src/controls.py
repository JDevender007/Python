from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.config import (
    BUTTON_FONT,
    BUTTON_WIDTH,
    HEADING_FONT,
    PAD_X,
)

from src.colors import (
    PRIMARY,
    PRIMARY_HOVER,
    TEXT,
)


class ControlPanel(ttk.Frame):

    def __init__(self, parent, app):

        super().__init__(parent)

        self.app = app

        self.build()

    def build(self):

        ttk.Label(
            self,
            text="Controls",
            font=HEADING_FONT,
        ).pack(
            anchor="w",
            pady=(0, 10),
        )

        self.add_button(
            "Select Folder",
            self.app.select_folder,
        )

        self.add_button(
            "Refresh",
            self.app.refresh_files,
        )

        self.add_button(
            "Rename Files",
            self.app.rename_files,
        )

        self.add_button(
            "Undo Rename",
            self.app.undo_rename,
        )

        self.add_button(
            "Clear",
            self.app.clear_files,
        )

        ttk.Separator(self).pack(
            fill="x",
            pady=10,
        )

        ttk.Label(
            self,
            text="Prefix",
        ).pack(anchor="w")

        self.prefix = ttk.Entry(self)

        self.prefix.pack(
            fill="x",
            pady=5,
        )

        ttk.Label(
            self,
            text="Suffix",
        ).pack(anchor="w")

        self.suffix = ttk.Entry(self)

        self.suffix.pack(
            fill="x",
            pady=5,
        )

        ttk.Label(
            self,
            text="Replace",
        ).pack(anchor="w")

        self.replace_from = ttk.Entry(self)

        self.replace_from.pack(
            fill="x",
            pady=5,
        )

        ttk.Label(
            self,
            text="With",
        ).pack(anchor="w")

        self.replace_to = ttk.Entry(self)

        self.replace_to.pack(
            fill="x",
            pady=5,
        )

        ttk.Label(
            self,
            text="Remove",
        ).pack(anchor="w")

        self.remove_text = ttk.Entry(self)

        self.remove_text.pack(
            fill="x",
            pady=5,
        )

        self.numbering = tk.BooleanVar()

        ttk.Checkbutton(
            self,
            text="Sequential Numbering",
            variable=self.numbering,
        ).pack(
            anchor="w",
            pady=10,
        )

    def add_button(
        self,
        text,
        command,
    ):

        tk.Button(
            self,
            text=text,
            command=command,
            width=BUTTON_WIDTH,
            bg=PRIMARY,
            fg=TEXT,
            activebackground=PRIMARY_HOVER,
            relief="flat",
            font=BUTTON_FONT,
            cursor="hand2",
        ).pack(
            fill="x",
            padx=PAD_X,
            pady=4,
        )

    def get_options(self):

        return {
            "prefix": self.prefix.get(),
            "suffix": self.suffix.get(),
            "replace_from": self.replace_from.get(),
            "replace_to": self.replace_to.get(),
            "remove_text": self.remove_text.get(),
            "numbering": self.numbering.get(),
        }
