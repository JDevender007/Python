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
            text="Report Controls",
            font=HEADING_FONT,
        ).pack(
            anchor="w",
            pady=(0, 10),
        )

        self.add_button(
            "Open Excel",
            self.app.open_excel,
        )

        self.add_button(
            "Preview Data",
            self.app.preview_data,
        )

        self.add_button(
            "Generate Summary",
            self.app.generate_summary,
        )

        self.add_button(
            "Missing Report",
            self.app.generate_missing_report,
        )

        self.add_button(
            "Bar Chart",
            self.app.create_bar_chart,
        )

        self.add_button(
            "Pie Chart",
            self.app.create_pie_chart,
        )

        self.add_button(
            "Export Report",
            self.app.export_report,
        )

        self.add_button(
            "Clear",
            self.app.clear_all,
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
