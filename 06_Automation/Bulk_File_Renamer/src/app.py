from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from pathlib import Path

from src.config import *

from src.colors import *

from src.controls import ControlPanel

from src.file_handler import FileHandler

from src.preview import PreviewGenerator

from src.renamer import FileRenamer

from src.utils import *


class BulkFileRenamerApp:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title(WINDOW_TITLE)

        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self.root.minsize(
            MIN_WIDTH,
            MIN_HEIGHT,
        )

        self.root.configure(
            bg=BACKGROUND,
        )

        self.fullscreen = False

        self.file_handler = FileHandler()

        self.preview = PreviewGenerator()

        self.renamer = FileRenamer()

        self.create_variables()

        self.create_layout()

        self.create_left_panel()

        self.create_center_panel()

        self.create_right_panel()

        self.bind_shortcuts()

    def create_variables(self):

        self.folder_var = tk.StringVar(value="No Folder Selected")

        self.total_files_var = tk.StringVar(value="0")

        self.renamed_files_var = tk.StringVar(value="0")

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
            width=280,
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
            width=300,
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
            text="Files",
            font=TITLE_FONT,
            bg=BACKGROUND,
            fg=TEXT,
        )

        title.pack(
            anchor="w",
            pady=(0, 10),
        )

        columns = (
            "original",
            "preview",
            "size",
        )

        self.tree = ttk.Treeview(
            self.center_frame,
            columns=columns,
            show="headings",
        )

        self.tree.heading(
            "original",
            text="Original Name",
        )

        self.tree.heading(
            "preview",
            text="Preview Name",
        )

        self.tree.heading(
            "size",
            text="Size",
        )

        self.tree.column(
            "original",
            width=350,
        )

        self.tree.column(
            "preview",
            width=350,
        )

        self.tree.column(
            "size",
            width=120,
            anchor="center",
        )

        scrollbar = ttk.Scrollbar(
            self.center_frame,
            orient="vertical",
            command=self.tree.yview,
        )

        self.tree.configure(
            yscrollcommand=scrollbar.set,
        )

        self.tree.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar.pack(
            side="right",
            fill="y",
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
            "Selected Folder",
            self.folder_var,
        )

        self.create_stat(
            "Total Files",
            self.total_files_var,
        )

        self.create_stat(
            "Renamed Files",
            self.renamed_files_var,
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
            wraplength=240,
            justify="left",
            font=("Segoe UI", 10),
        ).pack(
            anchor="w",
        )

    def bind_shortcuts(self):

        self.root.bind(
            "<Control-o>",
            lambda event: self.select_folder(),
        )

        self.root.bind(
            "<Control-r>",
            lambda event: self.rename_files(),
        )

        self.root.bind(
            "<Control-l>",
            lambda event: self.refresh_files(),
        )

        self.root.bind(
            "<Control-z>",
            lambda event: self.undo_rename(),
        )

        self.root.bind(
            "<Delete>",
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

    def select_folder(self):

        folder = self.file_handler.select_folder()

        if folder is None:
            return

        self.folder_var.set(folder)

        self.refresh_files()

        self.set_status("Folder loaded successfully")

    def refresh_files(self):

        self.file_handler.refresh()

        self.refresh_tree()

        self.update_statistics()

    def refresh_tree(self):

        self.tree.delete(*self.tree.get_children())

        files = self.file_handler.get_files()

        if not files:
            return

        options = self.controls.get_options()

        preview_names = self.preview.generate(
            files,
            prefix=options["prefix"],
            suffix=options["suffix"],
            replace_from=options["replace_from"],
            replace_to=options["replace_to"],
            remove_text=options["remove_text"],
            numbering=options["numbering"],
        )

        for original, preview in zip(
            files,
            preview_names,
        ):

            self.tree.insert(
                "",
                tk.END,
                values=(
                    get_filename(original),
                    preview,
                    get_file_size_string(original),
                ),
            )

    def update_statistics(self):

        files = self.file_handler.get_files()

        self.total_files_var.set(str(len(files)))

        self.folder_var.set(
            self.file_handler.get_folder() if files else "No Folder Selected"
        )

        if files:

            self.status_var.set("Ready")

        else:

            self.status_var.set("No Files Loaded")

    def generate_preview(self):

        if self.file_handler.is_empty():
            return

        self.refresh_tree()

    def set_status(
        self,
        text: str,
    ):

        self.status_var.set(text)

        self.root.update_idletasks()

    def clear_files(self):

        if self.file_handler.is_empty():
            return

        answer = messagebox.askyesno("Clear Files", "Clear the current file list?")

        if not answer:
            return

        self.file_handler.clear()

        self.tree.delete(*self.tree.get_children())

        self.total_files_var.set("0")

        self.folder_var.set("No Folder Selected")

        self.status_var.set("Ready")

    def on_option_changed(self):

        self.generate_preview()

    def update_preview(self):

        self.generate_preview()

    def refresh_preview(self):

        self.generate_preview()

    def get_selected_files(self):

        files = []

        for item in self.tree.selection():

            index = self.tree.index(item)

            files.append(self.file_handler.get_files()[index])

        return files

    def select_all(self):

        for item in self.tree.get_children():

            self.tree.selection_add(item)

    def clear_selection(self):

        for item in self.tree.selection():

            self.tree.selection_remove(item)

    def update_after_operation(self):

        self.refresh_files()

        self.generate_preview()

    def rename_files(self):

        files = self.file_handler.get_files()

        if not files:

            messagebox.showwarning("No Files", "Please select a folder first.")

            return

        options = self.controls.get_options()

        preview_names = self.preview.generate(
            files,
            prefix=options["prefix"],
            suffix=options["suffix"],
            replace_from=options["replace_from"],
            replace_to=options["replace_to"],
            remove_text=options["remove_text"],
            numbering=options["numbering"],
        )

        answer = messagebox.askyesno("Rename Files", f"Rename {len(files)} files?")

        if not answer:
            return

        try:

            renamed = self.renamer.rename_files(
                files,
                preview_names,
            )

            self.renamed_files_var.set(str(renamed))

            self.set_status("Files renamed successfully")

            self.refresh_files()

            messagebox.showinfo("Success", f"{renamed} files renamed successfully.")

        except Exception as error:

            messagebox.showerror(
                "Rename Error",
                str(error),
            )

            self.set_status("Rename failed")

    def undo_rename(self):

        if not self.renamer.has_history():

            messagebox.showinfo("Undo", "Nothing to undo.")

            return

        try:

            self.renamer.undo()

            self.renamed_files_var.set("0")

            self.refresh_files()

            self.set_status("Rename operation undone")

            messagebox.showinfo("Undo", "Previous rename operation has been undone.")

        except Exception as error:

            messagebox.showerror(
                "Undo Error",
                str(error),
            )

    def rename_selected(self):

        selected = self.get_selected_files()

        if not selected:

            messagebox.showwarning("Selection", "Select one or more files.")

            return

        options = self.controls.get_options()

        preview_names = self.preview.generate(
            selected,
            prefix=options["prefix"],
            suffix=options["suffix"],
            replace_from=options["replace_from"],
            replace_to=options["replace_to"],
            remove_text=options["remove_text"],
            numbering=options["numbering"],
        )

        try:

            renamed = self.renamer.rename_files(
                selected,
                preview_names,
            )

            self.renamed_files_var.set(str(renamed))

            self.refresh_files()

            self.set_status("Selected files renamed")

        except Exception as error:

            messagebox.showerror(
                "Rename Error",
                str(error),
            )

    def reset_preview(self):

        self.controls.prefix.delete(
            0,
            tk.END,
        )

        self.controls.suffix.delete(
            0,
            tk.END,
        )

        self.controls.replace_from.delete(
            0,
            tk.END,
        )

        self.controls.replace_to.delete(
            0,
            tk.END,
        )

        self.controls.remove_text.delete(
            0,
            tk.END,
        )

        self.controls.numbering.set(False)

        self.generate_preview()

    def update_progress(
        self,
        value: int,
    ):

        if hasattr(self.controls, "progress"):

            self.controls.progress["value"] = value

            self.root.update_idletasks()

    def reset_progress(self):

        self.update_progress(0)

    def operation_started(
        self,
        text: str,
    ):

        self.set_status(text)

        self.reset_progress()

        if hasattr(self.controls, "disable"):

            self.controls.disable()

    def operation_finished(
        self,
        text: str,
    ):

        self.update_progress(100)

        self.set_status(text)

        if hasattr(self.controls, "enable"):

            self.controls.enable()

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

    def on_close(self):

        answer = messagebox.askyesno("Exit", "Do you want to exit the application?")

        if answer:

            self.root.destroy()

    def bind_events(self):

        self.controls.prefix.bind(
            "<KeyRelease>",
            lambda event: self.update_preview(),
        )

        self.controls.suffix.bind(
            "<KeyRelease>",
            lambda event: self.update_preview(),
        )

        self.controls.replace_from.bind(
            "<KeyRelease>",
            lambda event: self.update_preview(),
        )

        self.controls.replace_to.bind(
            "<KeyRelease>",
            lambda event: self.update_preview(),
        )

        self.controls.remove_text.bind(
            "<KeyRelease>",
            lambda event: self.update_preview(),
        )

        self.controls.numbering.trace_add(
            "write",
            lambda *args: self.update_preview(),
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close,
        )

    def initialize(self):

        self.bind_events()

        self.refresh_files()

        self.set_status("Ready")

        self.reset_progress()

    def show_about(self):

        messagebox.showinfo("About", "Bulk File Renamer\nVersion 1.0.0")

    def show_help(self):

        messagebox.showinfo(
            "Help",
            "Select a folder, configure rename options, preview changes, and rename files.",
        )

    def reset_application(self):

        self.file_handler.clear()

        self.tree.delete(*self.tree.get_children())

        self.folder_var.set("No Folder Selected")

        self.total_files_var.set("0")

        self.renamed_files_var.set("0")

        self.status_var.set("Ready")

        self.reset_preview()

        self.reset_progress()

    def save_settings(self):

        pass

    def load_settings(self):

        pass

    def run(self):

        self.initialize()

        self.root.mainloop()


def main():

    app = BulkFileRenamerApp()

    app.run()


if __name__ == "__main__":

    main()
