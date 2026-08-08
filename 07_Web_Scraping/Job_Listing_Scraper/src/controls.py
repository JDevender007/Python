from __future__ import annotations

import tkinter as tk

from src.colors import (
    PRIMARY,
    PRIMARY_HOVER,
    TEXT,
    SURFACE,
)

from src.config import (
    BUTTON_FONT,
    BUTTON_WIDTH,
    HEADING_FONT,
    PAD_X,
)


class ControlPanel(tk.Frame):

    def __init__(
        self,
        parent,
        app,
    ):

        super().__init__(
            parent,
            bg=SURFACE,
        )

        self.app = app

        self.build()

    def build(self):

        tk.Label(
            self,
            text="Job Controls",
            font=HEADING_FONT,
            bg=SURFACE,
            fg=TEXT,
        ).pack(
            anchor="w",
            padx=10,
            pady=(10, 15),
        )

        self.add_button(
            "Scrape Jobs",
            self.app.scrape_jobs,
        )

        self.add_button(
            "Apply Filters",
            self.app.apply_filters,
        )

        self.add_button(
            "Export CSV",
            self.app.export_csv,
        )

        self.add_button(
            "Export JSON",
            self.app.export_json,
        )

        self.add_button(
            "Clear Results",
            self.app.clear_results,
        )

    def add_button(
        self,
        text,
        command,
    ):

        button = tk.Button(
            self,
            text=text,
            command=command,
            width=BUTTON_WIDTH,
            bg=PRIMARY,
            fg=TEXT,
            activebackground=PRIMARY_HOVER,
            activeforeground=TEXT,
            relief="flat",
            font=BUTTON_FONT,
            cursor="hand2",
        )

        button.pack(
            fill="x",
            padx=PAD_X + 5,
            pady=4,
        )

    def disable(self):

        for child in self.winfo_children():

            try:

                child.configure(
                    state="disabled",
                )

            except tk.TclError:

                pass

    def enable(self):

        for child in self.winfo_children():

            try:

                child.configure(
                    state="normal",
                )

            except tk.TclError:

                pass
