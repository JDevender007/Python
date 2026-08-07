from __future__ import annotations

import tkinter as tk

from tkinter import ttk

from src.colors import (
    PRIMARY,
    PRIMARY_HOVER,
    TEXT,
)

from src.config import (
    BUTTON_FONT,
    BUTTON_WIDTH,
    HEADING_FONT,
    PAD_X,
)


class ControlPanel(ttk.Frame):

    def __init__(
        self,
        parent,
        app,
    ):

        super().__init__(parent)

        self.app = app

        self.build()

    def build(self):

        ttk.Label(
            self,
            text="Scraper Controls",
            font=HEADING_FONT,
        ).pack(
            anchor="w",
            pady=(0, 10),
        )

        self.add_button(
            "Scrape News",
            self.app.scrape_news,
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

    def disable(self):

        for child in self.winfo_children():

            try:

                child.configure(
                    state="disabled",
                )

            except Exception:

                pass

    def enable(self):

        for child in self.winfo_children():

            try:

                child.configure(
                    state="normal",
                )

            except Exception:

                pass
