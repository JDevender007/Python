from __future__ import annotations

import tkinter as tk

from tkinter import ttk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText

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
from src.email_sender import EmailSender
from src.template_manager import TemplateManager
from src.attachment_manager import AttachmentManager

from src.utils import (
    split_emails,
)


class EmailAutomationApp:

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

        self.sender = EmailSender()

        self.templates = TemplateManager()

        self.attachments = AttachmentManager()

        self.create_variables()

        self.create_layout()

        self.create_left_panel()

        self.create_center_panel()

        self.create_right_panel()

        self.bind_shortcuts()

    def create_variables(self):

        self.status_var = tk.StringVar(value="Disconnected")

        self.recipient_count_var = tk.StringVar(value="0")

        self.attachment_count_var = tk.StringVar(value="0")

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

        tk.Label(
            self.center_frame,
            text="Compose Email",
            font=TITLE_FONT,
            bg=BACKGROUND,
            fg=TEXT,
        ).pack(
            anchor="w",
            pady=(0, 15),
        )

        tk.Label(
            self.center_frame,
            text="Recipients",
            bg=BACKGROUND,
            fg=TEXT,
        ).pack(
            anchor="w",
        )

        self.recipient_entry = ScrolledText(
            self.center_frame,
            height=4,
        )

        self.recipient_entry.pack(
            fill="x",
            pady=(5, 10),
        )

        tk.Label(
            self.center_frame,
            text="Subject",
            bg=BACKGROUND,
            fg=TEXT,
        ).pack(
            anchor="w",
        )

        self.subject_entry = tk.Entry(
            self.center_frame,
        )

        self.subject_entry.pack(
            fill="x",
            pady=(5, 10),
        )

        tk.Label(
            self.center_frame,
            text="Message",
            bg=BACKGROUND,
            fg=TEXT,
        ).pack(
            anchor="w",
        )

        self.body_text = ScrolledText(
            self.center_frame,
            wrap="word",
        )

        self.body_text.pack(
            fill="both",
            expand=True,
        )

    def create_right_panel(self):

        tk.Label(
            self.right_frame,
            text="Information",
            font=TITLE_FONT,
            bg=BACKGROUND,
            fg=TEXT,
        ).pack(
            anchor="w",
            pady=(0, 15),
        )

        self.create_stat(
            "Status",
            self.status_var,
        )

        self.create_stat(
            "Recipients",
            self.recipient_count_var,
        )

        self.create_stat(
            "Attachments",
            self.attachment_count_var,
        )

        ttk.Progressbar(
            self.right_frame,
            maximum=100,
            variable=self.progress_var,
        ).pack(
            fill="x",
            pady=20,
        )

        self.attachment_list = tk.Listbox(
            self.right_frame,
            height=12,
        )

        self.attachment_list.pack(
            fill="both",
            expand=True,
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
        ).pack(
            anchor="w",
        )

    def bind_shortcuts(self):

        self.root.bind(
            "<Control-s>",
            lambda event: self.send_email(),
        )

        self.root.bind(
            "<Control-o>",
            lambda event: self.add_attachment(),
        )

        self.root.bind(
            "<Control-l>",
            lambda event: self.load_template(),
        )

        self.root.bind(
            "<Control-t>",
            lambda event: self.save_template(),
        )

        self.root.bind(
            "<Control-r>",
            lambda event: self.clear_form(),
        )

        self.root.bind(
            "<F11>",
            lambda event: self.toggle_fullscreen(),
        )

        self.root.bind(
            "<Escape>",
            lambda event: self.exit_fullscreen(),
        )

    def connect_server(self):

        email, password = self.controls.get_credentials()

        if not email or not password:

            messagebox.showwarning(
                "Credentials",
                "Enter your email and app password.",
            )

            return

        try:

            self.sender.connect(
                email,
                password,
            )

            self.status_var.set("Connected")

            messagebox.showinfo("Success", "Connected to SMTP server.")

        except Exception as error:

            self.status_var.set("Connection Failed")

            messagebox.showerror(
                "Connection Error",
                str(error),
            )

    def add_attachment(self):

        self.attachments.add_files()

        self.refresh_attachment_list()

    def clear_attachments(self):

        self.attachments.clear()

        self.refresh_attachment_list()

    def refresh_attachment_list(self):

        self.attachment_list.delete(
            0,
            tk.END,
        )

        files = self.attachments.get_files()

        for file in files:

            self.attachment_list.insert(
                tk.END,
                file,
            )

        self.attachment_count_var.set(str(self.attachments.total_files()))

    def save_template(self):

        subject = self.subject_entry.get().strip()

        body = self.body_text.get(
            "1.0",
            tk.END,
        ).strip()

        name = simpledialog.askstring(
            "Template",
            "Template Name",
        )

        if not name:

            return

        self.templates.save_template(
            name,
            subject,
            body,
        )

        messagebox.showinfo("Success", "Template saved successfully.")

    def load_template(self):

        templates = self.templates.get_templates()

        if not templates:

            messagebox.showinfo("Templates", "No templates available.")

            return

        name = simpledialog.askstring(
            "Load Template",
            "Template Name",
        )

        if not name:

            return

        data = self.templates.load_template(
            name,
        )

        if data is None:

            messagebox.showerror("Error", "Template not found.")

            return

        self.subject_entry.delete(
            0,
            tk.END,
        )

        self.subject_entry.insert(
            0,
            data["subject"],
        )

        self.body_text.delete(
            "1.0",
            tk.END,
        )

        self.body_text.insert(
            "1.0",
            data["body"],
        )

    def update_recipient_count(self):

        emails = split_emails(
            self.recipient_entry.get(
                "1.0",
                tk.END,
            )
        )

        self.recipient_count_var.set(str(len(emails)))

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

    def send_email(self):

        sender, password = self.controls.get_credentials()

        if not sender or not password:

            messagebox.showwarning(
                "Credentials",
                "Please enter your email credentials.",
            )

            return

        recipients = split_emails(
            self.recipient_entry.get(
                "1.0",
                tk.END,
            )
        )

        if not recipients:

            messagebox.showwarning(
                "Recipients",
                "Enter at least one recipient.",
            )

            return

        subject = self.subject_entry.get().strip()

        body = self.body_text.get(
            "1.0",
            tk.END,
        ).strip()

        if not subject:

            messagebox.showwarning(
                "Subject",
                "Subject cannot be empty.",
            )

            return

        if not body:

            messagebox.showwarning(
                "Message",
                "Message cannot be empty.",
            )

            return

        self.update_progress(10)

        self.set_status("Sending email...")

        try:

            self.sender.send_email(
                sender=sender,
                recipients=recipients,
                subject=subject,
                body=body,
                attachments=self.attachments.get_files(),
            )

            self.update_progress(100)

            self.set_status("Email sent successfully")

            messagebox.showinfo("Success", "Email sent successfully.")

        except Exception as error:

            self.reset_progress()

            self.set_status("Failed to send email")

            messagebox.showerror(
                "Error",
                str(error),
            )

    def send_bulk_email(self):

        self.send_email()

    def clear_form(self):

        self.recipient_entry.delete(
            "1.0",
            tk.END,
        )

        self.subject_entry.delete(
            0,
            tk.END,
        )

        self.body_text.delete(
            "1.0",
            tk.END,
        )

        self.clear_attachments()

        self.recipient_count_var.set("0")

        self.set_status("Ready")

        self.reset_progress()

    def refresh(self):

        self.update_recipient_count()

        self.refresh_attachment_list()

    def preview_email(self):

        recipients = self.recipient_entry.get(
            "1.0",
            tk.END,
        ).strip()

        subject = self.subject_entry.get().strip()

        body = self.body_text.get(
            "1.0",
            tk.END,
        ).strip()

        preview = tk.Toplevel(self.root)

        preview.title("Email Preview")

        preview.geometry("700x500")

        tk.Label(
            preview,
            text="Recipients",
            font=("Segoe UI", 10, "bold"),
        ).pack(
            anchor="w",
            padx=10,
            pady=(10, 0),
        )

        tk.Label(
            preview,
            text=recipients,
            justify="left",
            wraplength=650,
        ).pack(
            anchor="w",
            padx=10,
        )

        tk.Label(
            preview,
            text="Subject",
            font=("Segoe UI", 10, "bold"),
        ).pack(
            anchor="w",
            padx=10,
            pady=(10, 0),
        )

        tk.Label(
            preview,
            text=subject,
            justify="left",
            wraplength=650,
        ).pack(
            anchor="w",
            padx=10,
        )

        tk.Label(
            preview,
            text="Message",
            font=("Segoe UI", 10, "bold"),
        ).pack(
            anchor="w",
            padx=10,
            pady=(10, 0),
        )

        text = ScrolledText(
            preview,
        )

        text.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10,
        )

        text.insert(
            "1.0",
            body,
        )

        text.configure(
            state="disabled",
        )

    def bind_events(self):

        self.recipient_entry.bind(
            "<KeyRelease>",
            lambda event: self.update_recipient_count(),
        )

        self.subject_entry.bind(
            "<KeyRelease>",
            lambda event: self.update_progress(0),
        )

        self.body_text.bind(
            "<KeyRelease>",
            lambda event: self.update_progress(0),
        )

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

        answer = messagebox.askyesno(
            "Exit",
            "Do you want to close the application?",
        )

        if not answer:

            return

        try:

            self.sender.disconnect()

        except Exception:

            pass

        self.root.destroy()

    def initialize(self):

        self.bind_events()

        self.refresh()

        self.reset_progress()

        self.set_status("Ready")

    def show_about(self):

        messagebox.showinfo(
            "About",
            "Email Automation\nVersion 1.0.0\n\nProfessional Email Sender built with Python.",
        )

    def show_help(self):

        messagebox.showinfo(
            "Help",
            "1. Connect to Gmail SMTP.\n"
            "2. Enter recipient emails.\n"
            "3. Enter subject and message.\n"
            "4. Add attachments if needed.\n"
            "5. Click Send Email.",
        )

    def reset_application(self):

        self.clear_form()

        self.status_var.set("Disconnected")

        self.recipient_count_var.set("0")

        self.attachment_count_var.set("0")

        self.reset_progress()

    def disconnect_server(self):

        try:

            self.sender.disconnect()

            self.status_var.set("Disconnected")

            messagebox.showinfo(
                "Disconnected",
                "SMTP connection closed successfully.",
            )

        except Exception as error:

            messagebox.showerror(
                "Error",
                str(error),
            )

    def save_settings(self):

        pass

    def load_settings(self):

        pass

    def run(self):

        self.initialize()

        self.root.mainloop()


def main():

    app = EmailAutomationApp()

    app.run()


if __name__ == "__main__":

    main()
