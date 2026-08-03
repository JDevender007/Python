from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from colors import (
    BACKGROUND,
    PRIMARY,
    PRIMARY_HOVER,
    SURFACE,
    TEXT,
)

from config import (
    BUTTON_FONT,
    BUTTON_WIDTH,
    HEADING_FONT,
    PAD_X,
    PAD_Y,
)

class ControlPanel(ttk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent)

        self.app = app

        self.configure(padding=10)

        self.output_path = tk.StringVar()
        self.status = tk.StringVar(value="Ready")
        self.progress = tk.IntVar(value=0)

        self.build()

    def build(self):

        title = ttk.Label(
            self,
            text="PDF Controls",
            font=HEADING_FONT,
        )
        title.pack(fill="x", pady=(0, 15))

        self.add_button("Add PDF Files", self.app.add_files)
        self.add_button("Remove Selected", self.app.remove_selected)
        self.add_button("Move Up", self.app.move_up)
        self.add_button("Move Down", self.app.move_down)

        ttk.Separator(self).pack(fill="x", pady=8)

        self.add_button("Merge PDFs", self.app.merge_pdfs)
        self.add_button("Clear List", self.app.clear_files)

        ttk.Separator(self).pack(fill="x", pady=8)

        self.add_button("Browse Output", self.app.choose_output_folder)
        self.add_button("Open Output Folder", self.app.open_output_folder)

        ttk.Label(
            self,
            text="Output Folder",
            font=HEADING_FONT,
        ).pack(anchor="w", pady=(15, 5))

        self.output_entry = ttk.Entry(
            self,
            textvariable=self.output_path,
            state="readonly",
        )

        self.output_entry.pack(fill="x")

        ttk.Label(
            self,
            text="Progress",
            font=HEADING_FONT,
        ).pack(anchor="w", pady=(15, 5))

        self.progressbar = ttk.Progressbar(
            self,
            maximum=100,
            variable=self.progress,
            mode="determinate",
        )

        self.progressbar.pack(fill="x")

        ttk.Label(
            self,
            textvariable=self.status,
        ).pack(anchor="w", pady=(15, 0))

    def add_button(self, text, command):

        button = tk.Button(
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
        )

        button.pack(
            fill="x",
            padx=PAD_X,
            pady=4,
        )

    def set_output_folder(self, path: str):

        self.output_path.set(path)

    def set_status(self, text: str):

        self.status.set(text)

    def set_progress(self, value: int):

        self.progress.set(value)
        self.update_idletasks()

    def reset_progress(self):

        self.progress.set(0)

    def reset_status(self):

        self.status.set("Ready")

    def disable(self):

        for widget in self.winfo_children():
            if isinstance(widget, tk.Button):
                widget.configure(state="disabled")

    def enable(self):

        for widget in self.winfo_children():
            if isinstance(widget, tk.Button):
                widget.configure(state="normal")