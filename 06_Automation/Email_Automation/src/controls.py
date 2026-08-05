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
            text="Email Controls",
            font=HEADING_FONT,
        ).pack(
            anchor="w",
            pady=(0, 10),
        )

        self.add_button(
            "Connect",
            self.app.connect_server,
        )

        self.add_button(
            "Send Email",
            self.app.send_email,
        )

        self.add_button(
            "Add Attachment",
            self.app.add_attachment,
        )

        self.add_button(
            "Clear Attachments",
            self.app.clear_attachments,
        )

        self.add_button(
            "Save Template",
            self.app.save_template,
        )

        self.add_button(
            "Load Template",
            self.app.load_template,
        )

        self.add_button(
            "Clear Form",
            self.app.clear_form,
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
            text="SMTP Email",
        ).pack(
            anchor="w",
        )

        self.email = ttk.Entry(
            self,
        )

        self.email.pack(
            fill="x",
            pady=5,
        )

        ttk.Label(
            self,
            text="App Password",
        ).pack(
            anchor="w",
        )

        self.password = ttk.Entry(
            self,
            show="*",
        )

        self.password.pack(
            fill="x",
            pady=5,
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

    def get_credentials(self):

        return (
            self.email.get().strip(),
            self.password.get().strip(),
        )
