from __future__ import annotations

import tkinter as tk

from tkinter import ttk
from tkinter import messagebox

from src.config import (
    WINDOW_TITLE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    MIN_WIDTH,
    MIN_HEIGHT,
    TITLE_FONT,
)

from src.colors import (
    BACKGROUND,
    SURFACE,
    TEXT,
)

from src.controls import ControlPanel
from src.file_handler import FileHandler
from src.backup_manager import BackupManager
from src.scheduler import BackupScheduler

from src.utils import (
    get_folder_size,
    format_size,
)


class FolderBackupApp:

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

        self.backup_manager = BackupManager()

        self.scheduler = BackupScheduler()

        self.create_variables()

        self.create_layout()

        self.create_left_panel()

        self.create_center_panel()

        self.create_right_panel()

        self.bind_shortcuts()

    def create_variables(self):

        self.status_var = tk.StringVar(value="Ready")

        self.source_var = tk.StringVar(value="No Source Selected")

        self.destination_var = tk.StringVar(value="No Backup Folder Selected")

        self.files_var = tk.StringVar(value="0")

        self.folders_var = tk.StringVar(value="0")

        self.size_var = tk.StringVar(value="0 B")

        self.progress_var = tk.IntVar(value=0)

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
            width=300,
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
            width=320,
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

        tk.Label(
            self.center_frame,
            text="Folder Backup Tool",
            font=TITLE_FONT,
            bg=BACKGROUND,
            fg=TEXT,
        ).pack(
            anchor="w",
            pady=(0, 15),
        )

        tk.Label(
            self.center_frame,
            text="Backup Log",
            bg=BACKGROUND,
            fg=TEXT,
        ).pack(
            anchor="w",
        )

        self.log_text = tk.Text(
            self.center_frame,
            wrap="word",
        )

        self.log_text.pack(
            fill="both",
            expand=True,
            pady=10,
        )

    def create_right_panel(self):

        tk.Label(
            self.right_frame,
            text="Backup Information",
            font=TITLE_FONT,
            bg=BACKGROUND,
            fg=TEXT,
        ).pack(
            anchor="w",
            pady=(0, 15),
        )

        self.create_card(
            "Source Folder",
            self.source_var,
        )

        self.create_card(
            "Backup Folder",
            self.destination_var,
        )

        self.create_card(
            "Files",
            self.files_var,
        )

        self.create_card(
            "Folders",
            self.folders_var,
        )

        self.create_card(
            "Folder Size",
            self.size_var,
        )

        self.create_card(
            "Status",
            self.status_var,
        )

        ttk.Progressbar(
            self.right_frame,
            maximum=100,
            variable=self.progress_var,
        ).pack(
            fill="x",
            pady=20,
        )

    def create_card(
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
            justify="left",
            wraplength=260,
        ).pack(
            anchor="w",
        )

    def bind_shortcuts(self):

        self.root.bind(
            "<Control-o>",
            lambda event: self.select_source(),
        )

        self.root.bind(
            "<Control-d>",
            lambda event: self.select_destination(),
        )

        self.root.bind(
            "<Control-b>",
            lambda event: self.create_backup(),
        )

        self.root.bind(
            "<F11>",
            lambda event: self.toggle_fullscreen(),
        )

        self.root.bind(
            "<Escape>",
            lambda event: self.exit_fullscreen(),
        )

    def select_source(self):

        folder = self.file_handler.select_source()

        if not folder:

            return

        self.source_var.set(folder)

        self.update_statistics()

        self.write_log(f"Source folder selected:\n{folder}\n")

    def select_destination(self):

        folder = self.file_handler.select_destination()

        if not folder:

            return

        self.destination_var.set(folder)

        self.write_log(f"Backup folder selected:\n{folder}\n")

    def update_statistics(self):

        if not self.file_handler.has_source():

            return

        self.files_var.set(str(self.file_handler.get_total_files()))

        self.folders_var.set(str(self.file_handler.get_total_folders()))

        size = get_folder_size(self.file_handler.get_source())

        self.size_var.set(format_size(size))

    def create_backup(self):

        if not self.file_handler.has_source():

            messagebox.showwarning(
                "Source Folder",
                "Please select a source folder.",
            )

            return

        if not self.file_handler.has_destination():

            messagebox.showwarning(
                "Backup Folder",
                "Please select a backup folder.",
            )

            return

        self.controls.disable()

        self.update_progress(10)

        self.set_status("Creating backup...")

        try:

            backup = self.backup_manager.create_backup(
                self.file_handler.get_source(),
                self.file_handler.get_destination(),
            )

            self.update_progress(100)

            self.set_status("Backup completed")

            self.write_log(f"Backup created successfully\n{backup}\n")

            messagebox.showinfo(
                "Success",
                "Backup completed successfully.",
            )

        except Exception as error:

            self.reset_progress()

            self.set_status("Backup failed")

            messagebox.showerror(
                "Backup Error",
                str(error),
            )

        self.controls.enable()

    def verify_backup(self):

        history = self.backup_manager.get_history()

        if not history:

            messagebox.showinfo(
                "Verify",
                "No backup available.",
            )

            return

        source, backup = history[-1]

        verified = self.backup_manager.verify_backup(
            source,
            backup,
        )

        if verified:

            self.write_log("Backup verification successful.\n")

            messagebox.showinfo(
                "Verification",
                "Backup verified successfully.",
            )

        else:

            self.write_log("Backup verification failed.\n")

            messagebox.showerror(
                "Verification",
                "Backup verification failed.",
            )

    def write_log(
        self,
        text,
    ):

        self.log_text.insert(
            tk.END,
            text + "\n",
        )

        self.log_text.see(
            tk.END,
        )

    def update_progress(
        self,
        value,
    ):

        self.progress_var.set(value)

        self.root.update_idletasks()

    def reset_progress(self):

        self.progress_var.set(0)

    def set_status(
        self,
        text,
    ):

        self.status_var.set(text)

        self.root.update_idletasks()

    def start_scheduler(self):

        try:

            interval = self.controls.get_interval()

        except ValueError:

            messagebox.showerror(
                "Invalid Interval",
                "Enter a valid number of seconds.",
            )

            return

        if self.scheduler.is_running():

            messagebox.showinfo(
                "Scheduler",
                "Scheduler is already running.",
            )

            return

        self.scheduler.start(
            interval,
            self.scheduled_backup,
        )

        self.set_status("Scheduler Running")

        self.write_log(f"Scheduler started ({interval} seconds).\n")

        messagebox.showinfo(
            "Scheduler",
            "Automatic backup started.",
        )

    def stop_scheduler(self):

        if not self.scheduler.is_running():

            return

        self.scheduler.stop()

        self.set_status("Scheduler Stopped")

        self.write_log("Scheduler stopped.\n")

        messagebox.showinfo(
            "Scheduler",
            "Automatic backup stopped.",
        )

    def scheduled_backup(self):

        try:

            backup = self.backup_manager.create_backup(
                self.file_handler.get_source(),
                self.file_handler.get_destination(),
            )

            self.write_log(f"Scheduled backup completed\n{backup}\n")

        except Exception as error:

            self.write_log(f"Scheduled backup failed\n{error}\n")

    def clear_log(self):

        self.log_text.delete(
            "1.0",
            tk.END,
        )

        self.write_log("Log cleared.\n")

    def show_history(self):

        history = self.backup_manager.get_history()

        if not history:

            messagebox.showinfo(
                "History",
                "No backup history available.",
            )

            return

        self.log_text.delete(
            "1.0",
            tk.END,
        )

        for index, item in enumerate(
            history,
            start=1,
        ):

            source, backup = item

            self.write_log(f"{index}. {source}\n{backup}\n")

    def refresh(self):

        self.update_statistics()

        self.root.update_idletasks()

    def clear_all(self):

        self.file_handler.clear()

        self.backup_manager.clear_history()

        self.source_var.set("No Source Selected")

        self.destination_var.set("No Backup Folder Selected")

        self.files_var.set("0")

        self.folders_var.set("0")

        self.size_var.set("0 B")

        self.status_var.set("Ready")

        self.reset_progress()

        self.log_text.delete(
            "1.0",
            tk.END,
        )

    def export_history(self):

        history = self.backup_manager.get_history()

        if not history:

            messagebox.showinfo(
                "Export",
                "No history available.",
            )

            return

        with open(
            "backup_history.txt",
            "w",
            encoding="utf-8",
        ) as file:

            for source, backup in history:

                file.write(f"Source : {source}\n")

                file.write(f"Backup : {backup}\n\n")

        messagebox.showinfo(
            "Export",
            "Backup history exported successfully.",
        )

    def bind_events(self):

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close,
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

    def on_close(self):

        if self.scheduler.is_running():

            self.scheduler.stop()

        answer = messagebox.askyesno(
            "Exit",
            "Do you want to exit the application?",
        )

        if answer:

            self.root.destroy()

    def initialize(self):

        self.bind_events()

        self.refresh()

        self.reset_progress()

        self.set_status("Ready")

        self.write_log("Folder Backup Tool started.\n")

    def show_about(self):

        messagebox.showinfo(
            "About",
            "Folder Backup Tool\nVersion 1.0.0\n\nDeveloped with Python and Tkinter.",
        )

    def show_help(self):

        messagebox.showinfo(
            "Help",
            "1. Select a source folder.\n"
            "2. Select a backup folder.\n"
            "3. Click Create Backup.\n"
            "4. Verify the backup.\n"
            "5. Use Scheduler for automatic backups.",
        )

    def reset_application(self):

        self.clear_all()

        self.scheduler.stop()

        self.status_var.set("Ready")

        self.reset_progress()

    def update_window_title(self):

        self.root.title(f"{WINDOW_TITLE} - {self.status_var.get()}")

    def heartbeat(self):

        self.update_window_title()

        self.root.after(
            1000,
            self.heartbeat,
        )

    def save_settings(self):

        pass

    def load_settings(self):

        pass

    def run(self):

        self.initialize()

        self.heartbeat()

        self.root.mainloop()


def main():

    app = FolderBackupApp()

    app.run()


if __name__ == "__main__":

    main()
