from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from pathlib import Path

from config import (
    WINDOW_TITLE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    MIN_WIDTH,
    MIN_HEIGHT,
    TITLE_FONT,
)

from colors import (
    BACKGROUND,
    SURFACE,
    TEXT,
)

from controls import ControlPanel
from file_handler import FileHandler
from pdf_manager import PDFManager
from merger import PDFMergerEngine

from utils import (
    total_pages,
    total_size,
    open_folder,
)

class PDFMergerApp:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title(WINDOW_TITLE)

        self.root.geometry(
            f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
        )

        self.root.minsize(
            MIN_WIDTH,
            MIN_HEIGHT,
        )

        self.root.configure(
            bg=BACKGROUND,
        )

        self.fullscreen = False

        self.file_handler = FileHandler()

        self.pdf_manager = PDFManager()

        self.merger = PDFMergerEngine()

        self.output_folder = str(Path.home())

        self.create_variables()

        self.create_layout()

        self.create_left_panel()

        self.create_center_panel()

        self.create_right_panel()

        self.bind_shortcuts()

    def create_variables(self):

        self.total_files_var = tk.StringVar(value="0")

        self.total_pages_var = tk.StringVar(value="0")

        self.total_size_var = tk.StringVar(value="0 B")

        self.status_var = tk.StringVar(value="Ready")

    def create_layout(self):

        self.main_frame = tk.Frame(
            self.root,
            bg=BACKGROUND,
        )

        self.main_frame.pack(
            fill="both",
            expand=True,
        )

        self.left_frame = tk.Frame(
            self.main_frame,
            bg=BACKGROUND,
            width=260,
        )

        self.left_frame.pack(
            side="left",
            fill="y",
            padx=10,
            pady=10,
        )

        self.center_frame = tk.Frame(
            self.main_frame,
            bg=BACKGROUND,
        )

        self.center_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=10,
            pady=10,
        )

        self.right_frame = tk.Frame(
            self.main_frame,
            bg=BACKGROUND,
            width=260,
        )

        self.right_frame.pack(
            side="right",
            fill="y",
            padx=10,
            pady=10,
        )

    def create_left_panel(self):

        self.controls = ControlPanel(
            self.left_frame,
            self,
        )

        self.controls.pack(
            fill="both",
            expand=True,
        )

    def create_center_panel(self):

        title = tk.Label(
            self.center_frame,
            text="PDF Files",
            font=TITLE_FONT,
            bg=BACKGROUND,
            fg=TEXT,
        )

        title.pack(
            anchor="w",
            pady=(0, 10),
        )

        self.listbox = tk.Listbox(
            self.center_frame,
            selectmode=tk.SINGLE,
            font=("Segoe UI", 11),
            bg=SURFACE,
            fg=TEXT,
            activestyle="none",
        )

        self.listbox.pack(
            fill="both",
            expand=True,
        )

        scrollbar = ttk.Scrollbar(
            self.listbox,
            orient="vertical",
            command=self.listbox.yview,
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        self.listbox.config(
            yscrollcommand=scrollbar.set,
        )

    def create_right_panel(self):

        title = tk.Label(
            self.right_frame,
            text="Statistics",
            font=TITLE_FONT,
            bg=BACKGROUND,
            fg=TEXT,
        )

        title.pack(
            anchor="w",
            pady=(0, 15),
        )

        self.create_stat(
            "Total Files",
            self.total_files_var,
        )

        self.create_stat(
            "Total Pages",
            self.total_pages_var,
        )

        self.create_stat(
            "Total Size",
            self.total_size_var,
        )

        self.create_stat(
            "Status",
            self.status_var,
        )

    def create_stat(
        self,
        title,
        variable,
    ):

        frame = tk.Frame(
            self.right_frame,
            bg=SURFACE,
            padx=10,
            pady=10,
        )

        frame.pack(
            fill="x",
            pady=6,
        )

        tk.Label(
            frame,
            text=title,
            bg=SURFACE,
            fg=TEXT,
            font=("Segoe UI", 10, "bold"),
        ).pack(
            anchor="w",
        )

        tk.Label(
            frame,
            textvariable=variable,
            bg=SURFACE,
            fg=TEXT,
            font=("Segoe UI", 11),
        ).pack(
            anchor="w",
        )

    def bind_shortcuts(self):

        self.root.bind(
            "<Control-o>",
            lambda event: self.add_files(),
        )

        self.root.bind(
            "<Control-m>",
            lambda event: self.merge_pdfs(),
        )

        self.root.bind(
            "<Delete>",
            lambda event: self.remove_selected(),
        )

        self.root.bind(
            "<Control-r>",
            lambda event: self.clear_files(),
        )

        self.root.bind(
            "<F11>",
            lambda event: self.toggle_fullscreen(),
        )

        self.root.bind(
            "<Escape>",
            lambda event: self.exit_fullscreen(),
        )

    def add_files(self):

        files = self.file_handler.select_pdf_files()

        if not files:
            return

        self.pdf_manager.load_files(files)

        self.refresh_list()

    def remove_selected(self):

        selection = self.listbox.curselection()

        if not selection:
            return

        index = selection[0]

        self.file_handler.remove_file(index)

        self.pdf_manager.load_files(
            self.file_handler.get_files()
        )

        self.refresh_list()

    def move_up(self):

        selection = self.listbox.curselection()

        if not selection:
            return

        index = selection[0]

        new_index = self.file_handler.move_up(index)

        self.pdf_manager.load_files(
            self.file_handler.get_files()
        )

        self.refresh_list()

        self.listbox.selection_set(new_index)

    def move_down(self):

        selection = self.listbox.curselection()

        if not selection:
            return

        index = selection[0]

        new_index = self.file_handler.move_down(index)

        self.pdf_manager.load_files(
            self.file_handler.get_files()
        )

        self.refresh_list()

        self.listbox.selection_set(new_index)

    def clear_files(self):

        if self.file_handler.is_empty():
            return

        answer = messagebox.askyesno(
            "Clear Files",
            "Remove all selected PDF files?"
        )

        if not answer:
            return

        self.file_handler.clear_files()

        self.pdf_manager.clear()

        self.refresh_list()

    def refresh_list(self):

        self.listbox.delete(0, tk.END)

        metadata = self.pdf_manager.get_metadata()

        for pdf in metadata:

            text = (
                f"{pdf['name']}   |   "
                f"{pdf['pages']} Pages   |   "
                f"{pdf['size']}"
            )

            self.listbox.insert(
                tk.END,
                text,
            )

        self.update_statistics()

    def update_statistics(self):

        files = self.file_handler.get_files()

        self.total_files_var.set(
            str(len(files))
        )

        self.total_pages_var.set(
            str(total_pages(files))
        )

        self.total_size_var.set(
            total_size(files)
        )

        if files:
            self.status_var.set("Ready")
        else:
            self.status_var.set("No PDF files selected")

    def choose_output_folder(self):

        folder = self.file_handler.choose_output_folder()

        if folder is None:
            return

        self.output_folder = folder

        self.controls.set_output_folder(folder)

        self.status_var.set(
            "Output folder updated"
        )

    def open_output_folder(self):

        open_folder(self.output_folder)

    def set_progress(
        self,
        value: int,
    ):

        self.controls.set_progress(value)

        self.root.update_idletasks()

    def reset_progress(self):

        self.controls.reset_progress()

    def set_status(
        self,
        text: str,
    ):

        self.status_var.set(text)

        self.controls.set_status(text)

        self.root.update_idletasks()

    def merge_pdfs(self):

        if not self.file_handler.validate_before_merge():
            return

        output_file = self.file_handler.choose_output_file()

        if output_file is None:
            return

        self.controls.disable()

        self.reset_progress()

        self.set_status("Merging PDFs...")

        success = self.merger.merge(
            self.file_handler.get_files(),
            output_file,
            self.set_progress,
        )

        self.controls.enable()

        if success:

            self.set_progress(100)

            self.set_status("Merge completed successfully")

            messagebox.showinfo(
                "Success",
                "PDF files merged successfully."
            )

        else:

            self.reset_progress()

            self.set_status("Merge failed")

            messagebox.showerror(
                "Error",
                "Failed to merge PDF files."
            )

    def toggle_fullscreen(self):

        self.fullscreen = not self.fullscreen

        self.root.attributes(
            "-fullscreen",
            self.fullscreen,
        )

    def exit_fullscreen(self):

        self.fullscreen = False

        self.root.attributes(
            "-fullscreen",
            False,
        )

    def run(self):

        self.root.mainloop()

def main():

    app = PDFMergerApp()

    app.run()


if __name__ == "__main__":

    main()