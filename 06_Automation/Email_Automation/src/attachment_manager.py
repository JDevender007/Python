from __future__ import annotations

from tkinter import filedialog


class AttachmentManager:

    def __init__(self):

        self.attachments = []

    def add_files(self):

        files = filedialog.askopenfilenames(title="Select Attachments")

        for file in files:

            if file not in self.attachments:

                self.attachments.append(file)

    def remove_file(
        self,
        index: int,
    ):

        if 0 <= index < len(self.attachments):

            self.attachments.pop(index)

    def clear(self):

        self.attachments.clear()

    def get_files(self):

        return self.attachments.copy()

    def total_files(self):

        return len(self.attachments)
