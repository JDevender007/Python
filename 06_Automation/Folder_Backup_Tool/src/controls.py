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
            text="Backup Controls",
            font=HEADING_FONT,
        ).pack(
            anchor="w",
            pady=(0, 10),
        )

        self.add_button(
            "Select Source",
            self.app.select_source,
        )

        self.add_button(
            "Select Backup Folder",
            self.app.select_destination,
        )

        self.add_button(
            "Create Backup",
            self.app.create_backup,
        )

        self.add_button(
            "Verify Backup",
            self.app.verify_backup,
        )

        self.add_button(
            "Start Scheduler",
            self.app.start_scheduler,
        )

        self.add_button(
            "Stop Scheduler",
            self.app.stop_scheduler,
        )

        self.add_button(
            "Clear",
            self.app.clear_all,
        )

        ttk.Separator(
            self,
            orient="horizontal",
        ).pack(
            fill="x",
            pady=12,
        )

        ttk.Label(
            self,
            text="Interval (seconds)",
        ).pack(
            anchor="w",
        )

        self.interval = ttk.Entry(
            self,
        )

        self.interval.insert(
            0,
            "60",
        )

        self.interval.pack(
            fill="x",
            pady=5,
        )

    def get_interval(self):

        value = self.interval.get().strip()

        if not value:

            return 60

        return int(value)

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
